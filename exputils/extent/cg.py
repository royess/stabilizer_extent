import numpy as np
import scipy.sparse
from exputils.extent.custom import calculate_extent_custom
from exputils.dot.get_topK_Amat import get_topK_Amat


def calculate_extent_CG(
    n: int, psi: np.ndarray, method: str = "mosek", verbose=False
) -> tuple:
    # Even if verbose=False, print some log.
    print(f"CG: {n=}, {method=}")
    print("start: calculate dots")
    K = 10000 if n <= 8 else 100000
    current_Amat = get_topK_Amat(n, psi, False, K, True)
    iter_max = 30
    eps = 1e-8
    discard_current_threshold = 0.8
    violation_max = 100000
    extends = []
    max_values = []
    for it in range(iter_max):
        print(f"iteration: {it + 1} / {iter_max}, Amat.shape = {current_Amat.shape}")
        print("start: solve SOCP")
        stabilizer_extent, coeff, dual = calculate_extent_custom(
            n, current_Amat, psi, method, verbose=verbose
        )
        extends.append(stabilizer_extent)
        print(f"{stabilizer_extent=}")
        print("start: calculate dual dots")
        dual_dots_state = get_topK_Amat(n, dual, True, K, True)
        if dual_dots_state.shape[1] == 0:
            print("OPTIMAL!")
            max_values.append(1.0)
            break
        assert np.all(np.count_nonzero(dual_dots_state.toarray(), axis=0) > 0)

        dual_dots = np.abs(dual.conj().T @ dual_dots_state)
        dual_violated_indices = dual_dots > 1 + eps
        violated_count = np.sum(dual_violated_indices)
        max_values.append(max(1.0, np.max(dual_dots) if len(dual_dots) > 0 else 0))
        print(f"# of violations(LB): {violated_count}")

        # restrict current Amat
        nonbasic_indices = np.abs(coeff) > eps
        critical_indices = np.abs(dual @ current_Amat) >= (
            discard_current_threshold - eps
        )
        remain_indices = np.logical_or(nonbasic_indices, critical_indices)
        current_Amat = current_Amat[:, remain_indices]
        if violated_count == 0:
            # this could happen if 1 < max(dual_dots) < 1+eps
            print("OPTIMAL!")
            break

        extra_size = min(violation_max, violated_count)
        extra_Amat = dual_dots_state[
            :, np.argpartition(dual_dots, -extra_size)[-extra_size:]
        ]
        current_Amat = scipy.sparse.hstack([current_Amat, extra_Amat])

    return stabilizer_extent, extends, max_values, dual


def test_calculate_extent_CG():
    from exputils.state.random_ket import make_random_quantum_state
    from exputils.extent.actual import calculate_extent_actual

    n = 4
    for seed in range(3):
        print("=" * 20)
        np.random.seed(seed)
        psi = make_random_quantum_state("pure", n, seed)
        psi_check = psi.copy()
        stabilizerExtent = calculate_extent_CG(n, psi)[0]
        print(f"{stabilizerExtent=}")
        stabilizerExtent_check = calculate_extent_actual(n, psi)[0]
        print(f"{stabilizerExtent_check=}")
        assert np.allclose(psi, psi_check, atol=1e-5)
        assert np.isclose(stabilizerExtent, stabilizerExtent_check, atol=1e-5)
        print("CORRECT!")

    print("All tests passed!")


if __name__ == "__main__":
    test_calculate_extent_CG()
