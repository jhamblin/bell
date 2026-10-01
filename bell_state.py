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
    args = parser.parse_args()

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


if __name__ == "__main__":
    main()
