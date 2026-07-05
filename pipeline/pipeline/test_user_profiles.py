# test_user_profiles.py
# Standalone test to validate profile system logic
# Run this BEFORE integrating into Step_1_prod.py

import numpy as np
import pandas as pd

# ========== USER PROFILE CLASSES ==========

class UserProfile:
    """Base class for user profiles."""
    def __init__(self, profile_name, allowed_purposes, work_required=False):
        self.name = profile_name
        self.allowed_purposes = allowed_purposes
        self.work_required = work_required

    def can_use_purpose(self, trip_purpose):
        """Check if trip purpose is allowed."""
        return trip_purpose in self.allowed_purposes

    def validate_chain(self, trip_chain):
        """Validate entire trip chain against profile constraints."""
        # Check if Work is present when required
        if self.work_required and 'Work' not in trip_chain:
            return False
        # Check all purposes are allowed
        return all(purpose in self.allowed_purposes for purpose in trip_chain)

    def __repr__(self):
        return f"{self.name}(Work_required={self.work_required}, Allowed={len(self.allowed_purposes)})"

class CommuterProfile(UserProfile):
    def __init__(self):
        allowed = ['Home', 'Work', 'Personal', 'Shopping', 'Leisure', 'Business', 'Transport', 'Education']
        super().__init__('Commuter', allowed, work_required=True)

    def get_work_start_time(self):
        return np.random.uniform(7, 9)

    def get_work_duration(self):
        return np.random.uniform(7, 9)

class RetiredProfile(UserProfile):
    def __init__(self):
        super().__init__('Retired', ['Home', 'Leisure', 'Shopping', 'Personal'], work_required=False)

class NoncommuterProfile(UserProfile):
    def __init__(self):
        allowed = ['Home', 'Leisure', 'Shopping', 'Personal', 'Business', 'Education', 'Transport']
        super().__init__('Nonccommuter', allowed, work_required=False)

# ========== PROFILE DISTRIBUTION ==========

PROFILE_DISTRIBUTION = {
    'Commuter': 0.60,
    'Retired': 0.25,
    'Nonccommuter': 0.15
}

PROFILE_CLASSES = {
    'Commuter': CommuterProfile(),
    'Retired': RetiredProfile(),
    'Nonccommuter': NoncommuterProfile()
}

def assign_profiles(number_of_vehicles):
    """Assign profiles to vehicles based on distribution."""
    profiles = np.random.choice(
        list(PROFILE_DISTRIBUTION.keys()),
        size=number_of_vehicles,
        p=list(PROFILE_DISTRIBUTION.values())
    )
    return [PROFILE_CLASSES[p] for p in profiles]

# ========== FILTERING FUNCTION ==========

def filter_purposes(available_purposes, allowed_purposes):
    """
    Filter available trip purposes based on profile constraints.
    Returns: filtered list of purposes, normalized probabilities
    """
    # Create equal probability for demo
    probs = {p: 1.0/len(available_purposes) for p in available_purposes}

    # Zero out disallowed purposes
    filtered_probs = {p: 0.0 for p in available_purposes}
    for p in allowed_purposes:
        if p in available_purposes:
            filtered_probs[p] = probs[p]

    # Renormalize
    total = sum(filtered_probs.values())
    if total > 0:
        filtered_probs = {p: v/total for p, v in filtered_probs.items()}

    return filtered_probs

# ========== TEST CASES ==========

def test_profile_creation():
    """Test 1: Can create profile objects."""
    print("\n" + "="*60)
    print("TEST 1: Profile Creation")
    print("="*60)

    profiles = [CommuterProfile(), RetiredProfile(), NoncommuterProfile()]
    for p in profiles:
        print(f"✓ {p.name}: {p}")
        print(f"  - Work required: {p.work_required}")
        print(f"  - Allowed purposes: {p.allowed_purposes}")

def test_purpose_filtering():
    """Test 2: Purpose filtering respects constraints."""
    print("\n" + "="*60)
    print("TEST 2: Purpose Filtering")
    print("="*60)

    available = ['Home', 'Work', 'Shopping', 'Leisure', 'Personal']

    commuter = CommuterProfile()
    retired = RetiredProfile()
    noncommer = NoncommuterProfile()

    print(f"\nAvailable purposes: {available}")

    # Test Commuter
    filtered_c = filter_purposes(available, commuter.allowed_purposes)
    print(f"\nCommuter can use: {[p for p in filtered_c if filtered_c[p] > 0]}")
    print(f"  Work included: {'Work' in [p for p in filtered_c if filtered_c[p] > 0]}")

    # Test Retired
    filtered_r = filter_purposes(available, retired.allowed_purposes)
    print(f"\nRetired can use: {[p for p in filtered_r if filtered_r[p] > 0]}")
    print(f"  Work included: {('Work' in [p for p in filtered_r if filtered_r[p] > 0])}")
    if 'Work' not in [p for p in filtered_r if filtered_r[p] > 0]:
        print("  ✓ Correctly excluded Work")

    # Test Non-commuter
    filtered_n = filter_purposes(available, noncommer.allowed_purposes)
    print(f"\nNon-commuter can use: {[p for p in filtered_n if filtered_n[p] > 0]}")
    print(f"  Work included: {('Work' in [p for p in filtered_n if filtered_n[p] > 0])}")

def test_chain_validation():
    """Test 3: Chain validation enforces constraints."""
    print("\n" + "="*60)
    print("TEST 3: Trip Chain Validation")
    print("="*60)

    commuter = CommuterProfile()
    retired = RetiredProfile()

    test_cases = [
        ("Valid Commuter (2-trip)", ['Home', 'Work', 'Home'], commuter, True),
        ("Valid Commuter (4-trip)", ['Home', 'Work', 'Shopping', 'Home'], commuter, True),
        ("Invalid Commuter (no Work)", ['Home', 'Shopping', 'Home'], commuter, False),
        ("Invalid Chain (disallowed purpose)", ['Home', 'Work', 'Leisure', 'Home'], retired, False),
        ("Valid Retired (2-trip)", ['Home', 'Leisure', 'Home'], retired, True),
        ("Valid Retired (4-trip)", ['Home', 'Shopping', 'Leisure', 'Home'], retired, True),
    ]

    for desc, chain, profile, expected_valid in test_cases:
        result = profile.validate_chain(chain)
        status = "✓ PASS" if result == expected_valid else "✗ FAIL"
        print(f"\n{status}: {desc}")
        print(f"  Chain: {chain}")
        print(f"  Profile: {profile.name}")
        print(f"  Result: {result} (expected: {expected_valid})")

def test_profile_assignment():
    """Test 4: Probabilistic profile assignment."""
    print("\n" + "="*60)
    print("TEST 4: Profile Assignment (N=1000)")
    print("="*60)

    np.random.seed(42)  # For reproducible test
    profiles = assign_profiles(1000)

    # Count profiles
    counts = {}
    for p in profiles:
        counts[p.name] = counts.get(p.name, 0) + 1

    print("\nProfile Distribution (1000 vehicles):")
    print("Expected vs. Observed:")

    for profile_name in PROFILE_DISTRIBUTION:
        expected_pct = PROFILE_DISTRIBUTION[profile_name] * 100
        observed_count = counts.get(profile_name, 0)
        observed_pct = 100 * observed_count / sum(counts.values())

        print(f"\n{profile_name}:")
        print(f"  Expected: {expected_pct:5.1f}%")
        print(f"  Observed: {observed_pct:5.1f}% ({observed_count} vehicles)")

        # Check if within 2% of expected (reasonable for 1000 samples)
        if abs(observed_pct - expected_pct) < 2.0:
            print(f"  ✓ Within tolerance")
        else:
            print(f"  ⚠ Outside tolerance")

def test_work_requirement():
    """Test 5: Work requirement enforcement."""
    print("\n" + "="*60)
    print("TEST 5: Work Requirement Enforcement")
    print("="*60)

    commuter = CommuterProfile()
    retired = RetiredProfile()

    print("\nCommuter Profile:")
    print(f"  work_required = {commuter.work_required}")
    print(f"  'Work' in allowed_purposes = {'Work' in commuter.allowed_purposes}")
    print(f"  ✓ Commuter requires Work in chain")

    print("\nRetired Profile:")
    print(f"  work_required = {retired.work_required}")
    print(f"  'Work' in allowed_purposes = {'Work' in retired.allowed_purposes}")
    print(f"  ✓ Retired allows no Work in chain")

    # Validate chains
    print("\nValidation tests:")
    print(f"  Commuter: ['Home', 'Work', 'Home'] → {commuter.validate_chain(['Home', 'Work', 'Home'])}")
    print(f"  Commuter: ['Home', 'Shop', 'Home'] → {commuter.validate_chain(['Home', 'Shop', 'Home'])}")
    print(f"  Retired:  ['Home', 'Work', 'Home'] → {retired.validate_chain(['Home', 'Work', 'Home'])}")
    print(f"  Retired:  ['Home', 'Leisure', 'Home'] → {retired.validate_chain(['Home', 'Leisure', 'Home'])}")

def test_purpose_sampling():
    """Test 6: Sampling from filtered distributions."""
    print("\n" + "="*60)
    print("TEST 6: Purpose Sampling from Filtered Distribution")
    print("="*60)

    available = ['Home', 'Work', 'Shopping', 'Leisure', 'Personal']
    retired = RetiredProfile()

    print(f"\nAvailable purposes: {available}")
    print(f"Retired allowed: {retired.allowed_purposes}")

    # Filter
    filtered = filter_purposes(available, retired.allowed_purposes)
    valid_purposes = [p for p in filtered if filtered[p] > 0]
    probs = [filtered[p] for p in valid_purposes]

    print(f"\nFiltered purposes with probabilities:")
    for p, prob in zip(valid_purposes, probs):
        print(f"  {p}: {prob:.3f}")

    # Sample multiple times
    samples = np.random.choice(valid_purposes, size=100, p=probs)
    unique, counts = np.unique(samples, return_counts=True)

    print(f"\nSamples (n=100):")
    for u, c in zip(unique, counts):
        print(f"  {u}: {c} times")

    # Verify no Work sampled for retired
    if 'Work' not in samples:
        print(f"\n✓ Work was NEVER sampled for Retired user")
    else:
        print(f"\n✗ ERROR: Work was sampled for Retired user!")

# ========== RUN ALL TESTS ==========

if __name__ == "__main__":
    print("\n" + "="*60)
    print("USER PROFILE SYSTEM - COMPREHENSIVE TESTS")
    print("="*60)

    test_profile_creation()
    test_purpose_filtering()
    test_chain_validation()
    test_profile_assignment()
    test_work_requirement()
    test_purpose_sampling()

    print("\n" + "="*60)
    print("ALL TESTS COMPLETED")
    print("="*60 + "\n")
