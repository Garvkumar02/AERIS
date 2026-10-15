import hashlib
import uuid
import random
from datetime import date, datetime
from typing import List, Tuple, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..models import Attendance, GateEvent, RoomPresence, MerkleCommitment

GENESIS_MERKLE_ROOT = "0" * 64

def hash_pair(left: str, right: str) -> str:
    """Computes SHA-256 hash of two concatenated 64-character hex strings."""
    return hashlib.sha256((left + right).encode("utf-8")).hexdigest()

def build_merkle_tree(leaf_hashes: List[str]) -> Tuple[str, List[List[str]], int]:
    """
    Constructs a deterministic binary Merkle Tree from a list of leaf hashes.
    Returns:
        (merkle_root, tree_levels, depth)
    """
    if not leaf_hashes:
        return GENESIS_MERKLE_ROOT, [[]], 0

    # Ensure all leaves are lowercase 64-char hex
    current_level = [h.strip().lower() for h in leaf_hashes if h and len(h.strip()) == 64]
    if not current_level:
        return GENESIS_MERKLE_ROOT, [[]], 0

    tree_levels = [current_level]

    while len(current_level) > 1:
        next_level = []
        # If odd number of nodes, duplicate the last node
        if len(current_level) % 2 == 1:
            current_level.append(current_level[-1])

        for i in range(0, len(current_level), 2):
            parent = hash_pair(current_level[i], current_level[i + 1])
            next_level.append(parent)

        tree_levels.append(next_level)
        current_level = next_level

    merkle_root = current_level[0]
    depth = len(tree_levels)
    return merkle_root, tree_levels, depth

def generate_merkle_proof(leaf_hash: str, tree_levels: List[List[str]]) -> Dict[str, Any]:
    """
    Generates an inclusion proof for a given leaf hash within the tree levels.
    Returns a dict with leaf_hash, merkle_root, and proof steps:
        [{"sibling": "...", "position": "left" | "right"}]
    """
    cleaned_leaf = leaf_hash.strip().lower()
    if not tree_levels or not tree_levels[0]:
        return {
            "leaf_hash": cleaned_leaf,
            "merkle_root": GENESIS_MERKLE_ROOT,
            "proof": [],
            "found": False
        }

    leaves = tree_levels[0]
    try:
        idx = leaves.index(cleaned_leaf)
    except ValueError:
        return {
            "leaf_hash": cleaned_leaf,
            "merkle_root": tree_levels[-1][0] if tree_levels[-1] else GENESIS_MERKLE_ROOT,
            "proof": [],
            "found": False
        }

    proof = []
    current_idx = idx

    for level in tree_levels[:-1]:
        # If odd length, duplicate for pairing
        working_level = list(level)
        if len(working_level) % 2 == 1:
            working_level.append(working_level[-1])

        if current_idx % 2 == 0:
            sibling_idx = current_idx + 1
            sibling = working_level[sibling_idx]
            proof.append({"sibling": sibling, "position": "right"})
        else:
            sibling_idx = current_idx - 1
            sibling = working_level[sibling_idx]
            proof.append({"sibling": sibling, "position": "left"})

        current_idx = current_idx // 2

    root = tree_levels[-1][0]
    return {
        "leaf_hash": cleaned_leaf,
        "merkle_root": root,
        "proof": proof,
        "found": True
    }

def verify_merkle_proof(leaf_hash: str, proof: List[Dict[str, str]], expected_root: str) -> bool:
    """
    Verifies that leaf_hash belongs to the tree with expected_root given the proof path.
    """
    current = leaf_hash.strip().lower()
    for step in proof:
        sibling = step.get("sibling", "").strip().lower()
        position = step.get("position", "right")

        if position == "left":
            current = hash_pair(sibling, current)
        else:
            current = hash_pair(current, sibling)

    return current == expected_root.strip().lower()

def anchor_daily_events_to_merkle(
    db: Session,
    target_day: date,
    user_id: Optional[str] = None,
    network: str = "ETHEREUM_SEPOLIA_ANCHOR"
) -> MerkleCommitment:
    """
    Collects all event hashes from Attendance, GateEvents, and RoomPresence for the target day,
    constructs the binary Merkle Tree, simulates blockchain notarization receipt,
    and commits a MerkleCommitment record to the database.
    """
    # 1. Fetch Attendance hashes for target_day
    att_hashes = [
        att.event_hash for att in
        db.query(Attendance.event_hash)
        .filter(Attendance.day == target_day, Attendance.event_hash.isnot(None))
        .all()
        if att.event_hash
    ]

    # 2. Fetch GateEvent hashes for target_day
    day_start = datetime.combine(target_day, datetime.min.time())
    day_end = datetime.combine(target_day, datetime.max.time())

    gate_hashes = [
        g.event_hash for g in
        db.query(GateEvent.event_hash)
        .filter(GateEvent.timestamp >= day_start, GateEvent.timestamp <= day_end, GateEvent.event_hash.isnot(None))
        .all()
        if g.event_hash
    ]

    # 3. Fetch RoomPresence hashes for target_day
    presence_hashes = [
        p.presence_hash for p in
        db.query(RoomPresence.presence_hash)
        .filter(RoomPresence.check_in_at >= day_start, RoomPresence.check_in_at <= day_end, RoomPresence.presence_hash.isnot(None))
        .all()
        if p.presence_hash
    ]

    # Combine & deduplicate leaf hashes deterministically
    all_leaves = sorted(list(set(att_hashes + gate_hashes + presence_hashes)))

    if not all_leaves:
        # Create a synthetic genesis leaf if day has zero events
        synthetic_leaf = hashlib.sha256(f"GENESIS_DAY_NO_EVENTS|{target_day.isoformat()}".encode("utf-8")).hexdigest()
        all_leaves = [synthetic_leaf]

    merkle_root, tree_levels, depth = build_merkle_tree(all_leaves)

    # Deterministic simulated tx hash & block number
    base_num = int(target_day.strftime("%Y%m%d"))
    block_number = 5820000 + (base_num % 100000)
    tx_entropy = f"{merkle_root}|{network}|{block_number}|{len(all_leaves)}"
    tx_hash = "0x" + hashlib.sha256(tx_entropy.encode("utf-8")).hexdigest()

    commitment = MerkleCommitment(
        day=target_day,
        merkle_root=merkle_root,
        anchor_network=network,
        transaction_hash=tx_hash,
        block_number=block_number,
        event_count=len(all_leaves),
        tree_depth=depth,
        leaf_hashes=all_leaves,
        status="ANCHORED_ON_CHAIN",
        anchored_by_user_id=user_id,
        created_at=datetime.utcnow()
    )

    db.add(commitment)
    db.commit()
    db.refresh(commitment)
    return commitment
