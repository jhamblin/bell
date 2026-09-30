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

    result = device.run(circuit, shots=args.shots).result()
    counts = result.measurement_counts

    print("\nMeasurement counts:")
    for bitstring, count in sorted(counts.items()):
        print(f"  {bitstring}: {count}")


if __name__ == "__main__":
    main()
