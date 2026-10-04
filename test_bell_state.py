"""Tests for bell_state.py.

Run with:
    pip install -r requirements-dev.txt
    pytest

Covers: the circuit's exact state vector against the |Phi+> = (|00>+|11>)/sqrt(2)
math from the README, that a real run only ever measures 00/11 roughly
50/50 (never 01/10), get_device()'s ARN selection and local/qpu paths,
and wait_for_result()'s task-ID-printing and cancel-on-interrupt behavior.
"""

import numpy as np
import pytest
from braket.devices import LocalSimulator

import bell_state as bs


# --- The circuit itself, against the README's exact math -------------------


def test_build_bell_circuit_matches_exact_state_vector():
    circuit = bs.build_bell_circuit()
    circuit.state_vector()
    result = LocalSimulator().run(circuit, shots=0).result()
    state_vector = result.values[0]
    expected = np.array([1, 0, 0, 1]) / np.sqrt(2)  # (|00> + |11>) / sqrt(2)
    assert np.allclose(state_vector, expected)


def test_measurements_are_only_00_or_11():
    """The entanglement signature from the README: only 00/11 ever appear,
    split roughly 50/50 -- never 01/10."""
    circuit = bs.build_bell_circuit()
    result = LocalSimulator().run(circuit, shots=2000).result()
    counts = result.measurement_counts

    assert set(counts) <= {"00", "11"}
    total = sum(counts.values())
    assert counts.get("00", 0) / total == pytest.approx(0.5, abs=0.05)
    assert counts.get("11", 0) / total == pytest.approx(0.5, abs=0.05)


# --- get_device --------------------------------------------------------


def test_get_device_local_needs_no_aws_credentials():
    device = bs.get_device("local", None)
    assert isinstance(device, LocalSimulator)


def test_get_device_qpu_requires_an_arn():
    with pytest.raises(SystemExit):
        bs.get_device("qpu", None)


@pytest.mark.parametrize(
    "name,expected_arn",
    [
        ("sv1", "arn:aws:braket:::device/quantum-simulator/amazon/sv1"),
        ("dm1", "arn:aws:braket:::device/quantum-simulator/amazon/dm1"),
        ("tn1", "arn:aws:braket:::device/quantum-simulator/amazon/tn1"),
    ],
)
def test_get_device_managed_simulators_use_correct_arn(name, expected_arn, monkeypatch):
    """get_device() constructs a real AwsDevice, which hits the network on
    init (device-capabilities lookup) and needs AWS credentials -- so
    AwsDevice itself is faked here rather than actually constructed."""
    import braket.aws

    captured = {}

    class FakeAwsDevice:
        def __init__(self, arn):
            captured["arn"] = arn

    monkeypatch.setattr(braket.aws, "AwsDevice", FakeAwsDevice)

    bs.get_device(name, None)
    assert captured["arn"] == expected_arn


def test_get_device_qpu_passes_through_the_given_arn(monkeypatch):
    import braket.aws

    captured = {}

    class FakeAwsDevice:
        def __init__(self, arn):
            captured["arn"] = arn

    monkeypatch.setattr(braket.aws, "AwsDevice", FakeAwsDevice)

    bs.get_device("qpu", "arn:aws:braket:us-east-1::device/qpu/ionq/Forte-1")
    assert captured["arn"] == "arn:aws:braket:us-east-1::device/qpu/ionq/Forte-1"


# --- format_shot_outcomes / print_task_details / save_raw_results ---------


def test_format_shot_outcomes_matches_measurement_counts():
    """Per-shot bitstrings should tally up to the same aggregated counts
    `measurement_counts` reports."""
    circuit = bs.build_bell_circuit()
    result = LocalSimulator().run(circuit, shots=200).result()

    outcomes = bs.format_shot_outcomes(result)
    assert len(outcomes) == 200
    assert set(outcomes) <= {"00", "11"}

    from collections import Counter

    assert Counter(outcomes) == result.measurement_counts


def test_print_task_details_notes_untracked_metadata_for_local_runs(capsys):
    """The local simulator's task has no AWS-tracked metadata (task.metadata()
    returns None) -- this should be reported clearly, not raise."""
    circuit = bs.build_bell_circuit()
    task = LocalSimulator().run(circuit, shots=10)
    result = task.result()

    bs.print_task_details(task, result)
    out = capsys.readouterr().out
    assert "not tracked for the local simulator" in out


def test_print_task_details_prints_metadata_and_provider_fields(capsys):
    class FakeAdditionalMetadata:
        simulatorMetadata = "sim-meta"
        ionqMetadata = None
        rigettiMetadata = None
        oqcMetadata = None
        iqmMetadata = None
        xanaduMetadata = None
        queraMetadata = None
        dwaveMetadata = None

    class FakeResult:
        additional_metadata = FakeAdditionalMetadata()

    class FakeTask:
        def metadata(self):
            return {"status": "COMPLETED", "shots": 100, "deviceArn": "arn:fake"}

    bs.print_task_details(FakeTask(), FakeResult())
    out = capsys.readouterr().out
    assert "status: COMPLETED" in out
    assert "deviceArn: arn:fake" in out
    assert "simulatorMetadata: sim-meta" in out


def test_save_raw_results_downloads_from_the_tasks_s3_location(monkeypatch, tmp_path):
    captured = {}

    class FakeBody:
        def read(self):
            return b'{"fake": "results"}'

    class FakeS3Client:
        def get_object(self, Bucket, Key):
            captured["bucket"] = Bucket
            captured["key"] = Key
            return {"Body": FakeBody()}

    class FakeBoto3:
        def client(self, name):
            assert name == "s3"
            return FakeS3Client()

    import sys

    monkeypatch.setitem(sys.modules, "boto3", FakeBoto3())

    class FakeTask:
        def metadata(self):
            return {"outputS3Bucket": "my-bucket", "outputS3Directory": "tasks/abc"}

    path = tmp_path / "results.json"
    bs.save_raw_results(FakeTask(), str(path))

    assert captured == {"bucket": "my-bucket", "key": "tasks/abc/results.json"}
    assert path.read_bytes() == b'{"fake": "results"}'


# --- wait_for_result: task ID printing and Ctrl-C handling -----------------


def test_wait_for_result_returns_normally_without_interrupt():
    class FakeTask:
        id = "fake-id"

        def result(self):
            return "the result"

    assert bs.wait_for_result(FakeTask()) == "the result"


def test_wait_for_result_cancels_task_on_keyboard_interrupt():
    """Regression test: device.run(...).result() used to be called directly,
    so Ctrl-C only killed the local process -- the submitted task kept
    running (and billing) on AWS with no way to even find it again."""

    class FakeTask:
        id = "arn:aws:braket:us-west-2:123:quantum-task/fake"
        cancel_called = False

        def result(self):
            raise KeyboardInterrupt

        def cancel(self):
            self.cancel_called = True

    task = FakeTask()
    with pytest.raises(SystemExit):
        bs.wait_for_result(task)
    assert task.cancel_called


def test_wait_for_result_reports_but_does_not_raise_if_cancel_itself_fails():
    class FakeTask:
        id = "fake-id"

        def result(self):
            raise KeyboardInterrupt

        def cancel(self):
            raise RuntimeError("already completed")

    with pytest.raises(SystemExit):
        bs.wait_for_result(FakeTask())


def test_wait_for_result_raises_clearly_on_failed_task():
    """Regression test: task.result() returns None (not an exception) when
    a task fails -- e.g. a real QPU's compiler rejecting a circuit -- and
    the old code let that propagate into a confusing AttributeError on
    result.measurement_counts instead of a clear message."""

    class FakeTask:
        id = "fake-id"

        def result(self):
            return None

        def state(self):
            return "FAILED"

    with pytest.raises(SystemExit, match="FAILED"):
        bs.wait_for_result(FakeTask())


# --- CLI smoke test ----------------------------------------------------


def test_cli_runs_end_to_end():
    import os
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "bell_state.py", "--shots", "50"],
        cwd=os.path.dirname(os.path.abspath(__file__)) or ".",
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert "Measurement counts" in result.stdout


def test_cli_verbose_prints_per_shot_outcomes_and_task_metadata():
    import os
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "bell_state.py", "--shots", "20", "--verbose"],
        cwd=os.path.dirname(os.path.abspath(__file__)) or ".",
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert "Per-shot outcomes:" in result.stdout
    assert "shot 0:" in result.stdout
    assert "shot 19:" in result.stdout
    assert "Task metadata:" in result.stdout


def test_cli_save_raw_results_rejected_for_local_device():
    import os
    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable,
            "bell_state.py",
            "--shots",
            "10",
            "--save-raw-results",
            "/tmp/should-not-be-written.json",
        ],
        cwd=os.path.dirname(os.path.abspath(__file__)) or ".",
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode != 0
    assert "requires an AWS-backed device" in result.stderr
