import random
from itertools import combinations
import pandas as pd


def generate_fourballs(players_list, teams, matrix, strict_mode, shuffle_seed, player_modes):
    """
    GOAM‑correct fourball generator with cart balancing:
    - Distributes carting players as evenly as possible across groups
    - Same‑team allowed (soft penalty)
    - Repeat pairings strongly discouraged
    - Hybrid cart/walk logic (soft, on top of hard balancing)
    - Strict mode: only 3‑ and 4‑balls
    - Deterministic via shuffle_seed
    - Guests:
        * never added to matrix
        * never checked against matrix
        * no history penalty
    """
    random.seed(shuffle_seed)

    players = players_list[:]

    # ---------------------------------------------------------
    # PENALTY MATRIX (SOFT TEAM, STRONG HISTORY, SOFT CART/WALK)
    # ---------------------------------------------------------
    penalty = pd.DataFrame(0.0, index=players_list, columns=players_list)

    def is_guest(x: str) -> bool:
        return isinstance(x, str) and x.startswith("guest_")

    def history_penalty(a, b):
        if is_guest(a) or is_guest(b):
            return 0.0
        if a in matrix.index and b in matrix.columns:
            times = int(matrix.loc[a, b])
        else:
            times = 0
        return times * 50.0

    def team_penalty(a, b):
        ta = teams.get(a)
        tb = teams.get(b)
        if ta and tb and ta == tb:
            return 10.0
        return 0.0

    def cart_penalty(a, b):
        a_cart = "Carting" in player_modes.get(a, "")
        b_cart = "Carting" in player_modes.get(b, "")
        if a_cart and b_cart:
            return -2.0
        if a_cart != b_cart:
            return 1.0
        return 0.0

    for a, b in combinations(players_list, 2):
        p = history_penalty(a, b) + team_penalty(a, b) + cart_penalty(a, b)
        penalty.loc[a, b] = p
        penalty.loc[b, a] = p

    # ---------------------------------------------------------
    # GROUP SIZE PLANNING (STRICT MODE = ONLY 3s AND 4s)
    # ---------------------------------------------------------
    def plan_group_sizes(n):
        if not strict_mode:
            sizes = []
            while n > 4:
                sizes.append(4)
                n -= 4
            if n > 0:
                sizes.append(n)
            return sizes

        if n % 4 == 0:
            return [4] * (n // 4)
        if n % 4 == 1:
            if n >= 9:
                return [3, 3, 3] + [4] * ((n - 9) // 4)
            return [3, n - 3]
        if n % 4 == 2:
            return [3, 3] + [4] * ((n - 6) // 4)
        if n % 4 == 3:
            return [3] + [4] * ((n - 3) // 4)

    group_sizes = plan_group_sizes(len(players))

    # ---------------------------------------------------------
    # COST OF ADDING PLAYER p TO GROUP g
    # ---------------------------------------------------------
    def incremental_cost(g, p):
        c = sum(penalty.loc[p, x] for x in g)

        carts = sum("Carting" in player_modes.get(x, "") for x in g)
        walks = len(g) - carts
        p_cart = "Carting" in player_modes.get(p, "")

        target = len(g) + 1
        if target == 4:
            if p_cart and carts >= 2:
                c += 2.0
            if not p_cart and walks >= 2:
                c += 2.0
        elif target == 3:
            if p_cart and carts >= 2:
                c += 1.0
            if not p_cart and walks >= 2:
                c += 1.0

        return c

    # ---------------------------------------------------------
    # CART BALANCING: spread carts across groups first
    # ---------------------------------------------------------
    carting_players = [p for p in players if "Carting" in player_modes.get(p, "")]
    walking_players = [p for p in players if "Carting" not in player_modes.get(p, "")]

    random.shuffle(carting_players)
    random.shuffle(walking_players)

    num_groups = len(group_sizes)
    groups = [[] for _ in range(num_groups)]

    # assign carts as evenly as possible, respecting group size limits
    gi = 0
    for p in carting_players:
        # find next group with free slot
        attempts = 0
        while attempts < num_groups and len(groups[gi]) >= group_sizes[gi]:
            gi = (gi + 1) % num_groups
            attempts += 1
        groups[gi].append(p)
        gi = (gi + 1) % num_groups

    # remaining players to place via greedy logic
    remaining = walking_players[:]
    random.shuffle(remaining)

    # ---------------------------------------------------------
    # GREEDY GROUP BUILDING (FILL EXISTING GROUPS)
    # ---------------------------------------------------------
    for idx, size in enumerate(group_sizes):
        group = groups[idx]
        while len(group) < size and remaining:
            best_p = None
            best_cost = float("inf")

            for p in remaining:
                cost = incremental_cost(group, p)
                if cost < best_cost:
                    best_cost = cost
                    best_p = p

            group.append(best_p)
            remaining.remove(best_p)

    # ---------------------------------------------------------
    # LOCAL OPTIMISATION (SWAPS)
    # ---------------------------------------------------------
    def group_cost(g):
        return sum(penalty.loc[a, b] for a, b in combinations(g, 2))

    improved = True
    iters = 0
    while improved and iters < 200:
        improved = False
        iters += 1

        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                g1, g2 = groups[i], groups[j]

                for a in g1:
                    for b in g2:
                        new_g1 = [x for x in g1 if x != a] + [b]
                        new_g2 = [x for x in g2 if x != b] + [a]

                        if strict_mode and (len(new_g1) < 3 or len(new_g2) < 3):
                            continue

                        old = group_cost(g1) + group_cost(g2)
                        new = group_cost(new_g1) + group_cost(new_g2)

                        if new < old:
                            groups[i], groups[j] = new_g1, new_g2
                            improved = True

    # ---------------------------------------------------------
    # FINAL CLEANUP (STRICT MODE)
    # ---------------------------------------------------------
    if strict_mode:
        small = [g for g in groups if len(g) < 3]
        big = [g for g in groups if len(g) >= 3]

        for g in small:
            for p in g:
                best_g = None
                best_cost = float("inf")
                for h in big:
                    if len(h) >= 4:
                        continue
                    cost = incremental_cost(h, p)
                    if cost < best_cost:
                        best_cost = cost
                        best_g = h
                if best_g:
                    best_g.append(p)
                else:
                    big.append([p])

        groups = big

    return groups, penalty
