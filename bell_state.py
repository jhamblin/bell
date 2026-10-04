"""Prepare and measure a Bell state (|Φ+⟩) on Amazon Braket.

Runs the same two-gate circuit (H on qubit 0, then CNOT 0->1) against
either the local Braket simulator or a managed AWS device (simulator
or QPU). See README.md for the math behind what this circuit does.
"""

import argparse
from typing import Optional

from braket.circuits import Circuit
from braket.devices import LocalSimulator

# Fully-managed on-demand simulators available in Braket. See README.md
# for notes on cost and the AWS regions each one is available in.
MANAGED_SIMULATORS = {
    "sv1": "arn:aws:braket:::device/quantum-simulator/amazon/sv1",
    "dm1": "arn:aws:braket:::device/quantum-simulator/amazon/dm1",
    "tn1": "arn:aws:braket:::device/quantum-simulator/amazon/tn1",
}


def build_bell_circuit() -> Circuit:
    """Return the 2-qubit circuit that prepares |Φ+⟩ = (|00⟩ + |11⟩)/√2."""
    return Circuit().h(0).cnot(control=0, target=1)


def format_shot_outcomes(result) -> list:
    """Return each shot's measured bitstring, in shot order (as opposed to
    `measurement_counts`, which only gives the aggregated totals)."""
    return ["".join(str(bit) for bit in shot) for shot in result.measurements]


def print_task_details(task, result) -> None:
    """Print task metadata and device-specific fields from the raw
    results.json that aren't reflected in the measurement counts, e.g.
    execution timestamps and per-provider fields like IonQ's
    sharpened-probabilities flag."""
    metadata = task.metadata() or {}
    print("\nTask metadata:")
    printed_any = False
    for key in ("status", "shots", "deviceArn", "createdAt", "endedAt"):
        if key in metadata:
            print(f"  {key}: {metadata[key]}")
            printed_any = True
    if not printed_any:
        print("  (not tracked for the local simulator)")

    additional = result.additional_metadata
    for field in (
        "simulatorMetadata",
        "ionqMetadata",
        "rigettiMetadata",
        "oqcMetadata",
        "iqmMetadata",
        "xanaduMetadata",
        "queraMetadata",
        "dwaveMetadata",
    ):
        value = getattr(additional, field, None)
        if value is not None:
            print(f"  {field}: {value}")


def save_raw_results(task, path: str) -> None:
    """Download the raw results.json this task's result was parsed from and
    save it to `path`. Only applies to AWS-backed devices -- the local
    simulator has no S3-stored results.json."""
    import boto3

    metadata = task.metadata()
    bucket = metadata["outputS3Bucket"]
    key = f"{metadata['outputS3Directory']}/results.json"
    body = boto3.client("s3").get_object(Bucket=bucket, Key=key)["Body"].read()
    with open(path, "wb") as f:
        f.write(body)
    print(f"\nSaved raw results.json ({len(body)} bytes) to {path}")


def get_device(name: str, qpu_arn: Optional[str]):
    if name == "local":
        return LocalSimulator()

    # Imported lazily so `--device local` never requires AWS credentials.
    from braket.aws import AwsDevice

    if name == "qpu":
        if not qpu_arn:
            raise SystemExit("--qpu-arn is required when --device qpu")
        return AwsDevice(qpu_arn)

    return AwsDevice(MANAGED_SIMULATORS[name])


def wait_for_result(task):
    """Wait for a submitted quantum task's result, printing its ID so it
    can be found or cancelled manually (e.g. via the Braket console or
    `aws braket cancel-quantum-task`) even if this script is interrupted.

    Ctrl-C only stops this local process from waiting -- the task keeps
    running on AWS regardless. On KeyboardInterrupt, this requests
    cancellation of the task itself, but AWS cancels QPU tasks on a
    best-effort basis: once a task has started actually running on the
    device (as opposed to still queued), cancellation can fail and the
    task -- and its cost -- completes anyway.
    """
    print(f"Task ID: {task.id}")
    try:
        result = task.result()
    except KeyboardInterrupt:
        print("\nInterrupted -- requesting cancellation on AWS...")
        try:
            task.cancel()
            print(
                f"Cancellation requested for {task.id}. If the task had "
                "already started running, it may complete (and be billed) "
                "anyway -- check its status in the Braket console."
            )
        except Exception as e:
            print(f"Could not cancel: {e}")
        raise SystemExit(1)

    if result is None:
        # task.result() returns None (not an exception) on failure, after
        # printing its own failure reason -- e.g. a real QPU's compiler can
        # reject an accepted-gate-set circuit for being too large, which
        # isn't something retrying the same circuit fixes.
        raise SystemExit(
            f"Task {task.id} did not complete successfully "
            f"(state: {task.state()}). See the failure reason printed "
            "above, or check the task in the Braket console."
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--device",
        choices=["local", *MANAGED_SIMULATORS, "qpu"],
        default="local",
        help="Where to run the circuit (default: local).",
    )
    parser.add_argument(
        "--qpu-arn",
        default=None,
        help="Device ARN to use when --device qpu, e.g. "
        "arn:aws:braket:us-east-1::device/qpu/ionq/Aria-1",
    )
    parser.add_argument(
        "--shots", type=int, default=1000, help="Number of measurement shots."
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Also print each shot's individual outcome and task metadata "
        "(execution timestamps, device-specific fields) beyond the "
        "aggregated measurement counts.",
    )
    parser.add_argument(
        "--save-raw-results",
        metavar="PATH",
        default=None,
        help="Save the raw results.json this task's result was parsed from "
        "to PATH. Only applies to AWS-backed devices (sv1/dm1/tn1/qpu) -- "
        "the local simulator has no S3-stored results.json.",
    )
    args = parser.parse_args()

    if args.save_raw_results and args.device == "local":
        raise SystemExit(
            "--save-raw-results requires an AWS-backed device "
            "(sv1/dm1/tn1/qpu) -- the local simulator has no S3-stored "
            "results.json."
        )

    circuit = build_bell_circuit()
    print("Circuit:")
    print(circuit)
    print()

    device = get_device(args.device, args.qpu_arn)
    print(f"Running on {device}...")

    task = device.run(circuit, shots=args.shots)
    result = wait_for_result(task)
    counts = result.measurement_counts

    print("\nMeasurement counts:")
    for bitstring, count in sorted(counts.items()):
        print(f"  {bitstring}: {count}")

    if args.verbose:
        print("\nPer-shot outcomes:")
        for i, bitstring in enumerate(format_shot_outcomes(result)):
            print(f"  shot {i}: {bitstring}")
        print_task_details(task, result)

    if args.save_raw_results:
        save_raw_results(task, args.save_raw_results)


if __name__ == "__main__":
    main()
