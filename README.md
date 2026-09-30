# Bell State on Amazon Braket

A "hello world" for quantum computing on AWS Braket: prepare a two-qubit
Bell state, measure it, and see the entangled correlation come out in the
histogram of results. Runs identically against Braket's free local
simulator or a managed AWS simulator/QPU — same circuit, same code, just
a different `--device` flag.

```
q0: ──H──●──
         │
q1: ─────X──
```

## 1. The quantum mechanics, from scratch

### 1.1 Qubits and kets

A classical bit is 0 or 1. A **qubit** is a unit vector in a
2-dimensional complex vector space, written in **ket notation** as
`|ψ⟩`. The two basis states are:

```
|0⟩ = [1]      |1⟩ = [0]
      [0]            [1]
```

A general qubit state is a superposition:

```
|ψ⟩ = α|0⟩ + β|1⟩ = [α]
                     [β]
```

where `α, β ∈ ℂ` and `|α|² + |β|² = 1` (probabilities must sum to 1).
Measuring `|ψ⟩` in the computational basis yields `0` with probability
`|α|²` and `1` with probability `|β|²`, and the state then collapses to
whichever outcome was observed.

### 1.2 Multiple qubits and the tensor product

Two qubits live in a 4-dimensional space formed by the **tensor
product** `⊗` of the two individual spaces. The basis states are:

```
|00⟩ = |0⟩⊗|0⟩ = [1,0,0,0]ᵀ
|01⟩ = |0⟩⊗|1⟩ = [0,1,0,0]ᵀ
|10⟩ = |1⟩⊗|0⟩ = [0,0,1,0]ᵀ
|11⟩ = |1⟩⊗|1⟩ = [0,0,0,1]ᵀ
```

(Convention here: the first ket is qubit 0, the second is qubit 1; the
tensor product just stacks/expands the coordinates, e.g.
`[a,b]ᵀ ⊗ [c,d]ᵀ = [ac, ad, bc, bd]ᵀ`.)

A two-qubit state is **entangled** if it *cannot* be written as a
tensor product of two single-qubit states — i.e. you cannot describe
either qubit's state on its own, only the pair as a whole. That's
exactly what a Bell state is, and it's the reason Bell states are the
canonical demonstration of something quantum computers can do that
classical bits fundamentally cannot.

### 1.3 Gates are unitary matrices

A quantum gate is a unitary matrix `U` (one satisfying `U†U = I`) that
acts on the state vector by matrix multiplication: `|ψ'⟩ = U|ψ⟩`.
Unitarity is what keeps the result normalized (probabilities still sum
to 1) and reversible.

**Hadamard gate (H)** — acts on a single qubit, creates an equal
superposition:

```
H = 1/√2 * [1   1]
           [1  -1]

H|0⟩ = 1/√2 (|0⟩ + |1⟩)   =: |+⟩
H|1⟩ = 1/√2 (|0⟩ - |1⟩)   =: |−⟩
```

**CNOT gate (Controlled-NOT)** — acts on two qubits. It flips the
*target* qubit if and only if the *control* qubit is `|1⟩`, and leaves
it alone otherwise:

```
        |00⟩ |01⟩ |10⟩ |11⟩
CNOT = [ 1    0    0    0 ]  |00⟩
       [ 0    1    0    0 ]  |01⟩
       [ 0    0    0    1 ]  |10⟩
       [ 0    0    1    0 ]  |11⟩
```

i.e. `CNOT|00⟩ = |00⟩`, `CNOT|01⟩ = |01⟩`, `CNOT|10⟩ = |11⟩`,
`CNOT|11⟩ = |10⟩` (qubit 0 is the control, qubit 1 is the target).

### 1.4 Building the Bell state, step by step

Start both qubits in `|00⟩`. Apply `H` to qubit 0 only (qubit 1 is
untouched, i.e. the identity `I` acts on it), which as a joint
two-qubit operation is `H ⊗ I`:

```
(H ⊗ I) |00⟩ = (H|0⟩) ⊗ (I|0⟩)
             = [1/√2 (|0⟩ + |1⟩)] ⊗ |0⟩
             = 1/√2 (|00⟩ + |10⟩)
```

Now apply `CNOT` (control = qubit 0, target = qubit 1) to that
superposition. CNOT acts linearly on each term:

```
CNOT [1/√2 (|00⟩ + |10⟩)]
  = 1/√2 (CNOT|00⟩ + CNOT|10⟩)
  = 1/√2 (|00⟩ + |11⟩)
```

That final state is the Bell state `|Φ+⟩`:

```
|Φ+⟩ = 1/√2 (|00⟩ + |11⟩) = 1/√2 [1, 0, 0, 1]ᵀ
```

**Why this is entangled:** if you measure qubit 0, you get `0` or `1`
with 50/50 probability — but whichever you get, qubit 1 is now
*guaranteed* to collapse to the same value. Neither qubit has a
well-defined state on its own beforehand; only the pair does. No
combination of independent single-qubit states `(α|0⟩+β|1⟩)⊗(γ|0⟩+δ|1⟩)`
can produce `1/√2(|00⟩+|11⟩)` — try multiplying it out and you'll find
there's no `α,β,γ,δ` that works, which is the algebraic definition of
entanglement.

Running the circuit many times ("shots") and measuring both qubits
should therefore produce only `00` and `11` outcomes, each roughly
half the time, and *never* `01` or `10`. That's the signature you'll
see in the output of this script, and it's the experiment being run.

### 1.5 The other three Bell states

`|Φ+⟩` is one of four maximally-entangled two-qubit states that form
the **Bell basis**:

```
|Φ+⟩ = 1/√2 (|00⟩ + |11⟩)   ← this script
|Φ−⟩ = 1/√2 (|00⟩ − |11⟩)
|Ψ+⟩ = 1/√2 (|01⟩ + |10⟩)
|Ψ−⟩ = 1/√2 (|01⟩ − |10⟩)
```

You get the other three by tweaking the circuit: an `X` before the `H`
flips which pair of outcomes appears (`Φ→Ψ`), and a `Z` after the `H`
flips the relative sign (`+ → −`).

## 2. The code

[`bell_state.py`](bell_state.py) builds exactly the circuit above with
the Braket SDK:

```python
from braket.circuits import Circuit

circuit = Circuit().h(0).cnot(control=0, target=1)
```

and then submits it to whichever device you choose via `device.run(circuit,
shots=...)`, printing the resulting measurement-count histogram (e.g.
`{'00': 512, '11': 488}`).

## 3. Setup

Requires Python 3.9+ (tested with 3.9).

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 4. Running locally (no AWS account needed)

The default device is Braket's built-in local simulator, which runs
entirely on your machine — no AWS credentials, no cost, no network
calls:

```bash
python bell_state.py
```

Expect output like:

```
Measurement counts:
  00: 498
  11: 502
```

Use `--shots` to change the sample count:

```bash
python bell_state.py --shots 100
```

## 5. Running on AWS Braket

### 5.1 One-time AWS setup

1. Configure AWS credentials for a role/user with Braket permissions
   (e.g. `aws configure`, or an `AWS_PROFILE`/`AWS_ACCESS_KEY_ID` env
   var — anything the `boto3` credential chain picks up).
2. Braket requires an S3 bucket (in the same region as the device) to
   store task results, with a key prefix. Either:
   - Let Braket create/use the default bucket
     `amazon-braket-<region>-<account-id>`, or
   - Set one explicitly before running:
     ```bash
     export AWS_DEFAULT_REGION=us-east-1
     ```
     and pass a bucket via `AwsSession` if you want a non-default one
     (see the Braket SDK docs for `AwsSession(s3_destination_folder=...)`
     — not needed for the default bucket).

### 5.2 Run on a managed simulator

Fully-managed, on-demand simulators run in the cloud and are billed
per task/shot (see [Braket pricing](https://aws.amazon.com/braket/pricing/)
— SV1 is inexpensive but not free). `sv1` (state-vector) is the
standard choice for small circuits like this one:

```bash
python bell_state.py --device sv1
```

Other managed simulators: `dm1` (density matrix, supports noise
models) and `tn1` (tensor network, for larger qubit counts).

### 5.3 Run on real quantum hardware (QPU)

Pass the ARN of an available QPU. QPU availability, pricing, and
regions change over time — check the
[Braket console device list](https://console.aws.amazon.com/braket/home#/devices)
for current ARNs. Note that real hardware is noisy, so expect some
`01`/`10` outcomes in addition to the expected `00`/`11` — that's
physical error, not a bug.

```bash
python bell_state.py --device qpu --qpu-arn "arn:aws:braket:us-east-1::device/qpu/ionq/Aria-1" --shots 100
```

**QPU tasks cost real money per-shot and are billed even if you only
run a few shots — check current pricing before submitting.**

## 6. Interpreting the results

Whichever device you use, a correct run shows counts concentrated on
`00` and `11`, roughly split 50/50, with `01`/`10` at or near zero
(zero exactly on a noiseless simulator; small but nonzero on real
hardware due to gate/readout error). That correlation — despite each
individual qubit's outcome being random — is the experimental
signature of entanglement, and is the whole point of the circuit.
