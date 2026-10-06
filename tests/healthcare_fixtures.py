import pytest

from services.healthcare import service
from services.healthcare.access import Scope


@pytest.fixture
async def clinic(test_db):
    oid = await service.create_organization("1", "clinic", "Synthetic clinic")
    owner = Scope(oid, "1")
    a = await service.create_branch(owner, "A")
    b = await service.create_branch(owner, "B")
    for uid, role, branch in [
        ("2", "reception", a),
        ("3", "coordinator", a),
        ("4", "doctor", a),
        ("5", "assistant", a),
        ("6", "reception", b),
        ("7", "manager", None),
        ("8", "doctor", a),
    ]:
        await service.set_membership(owner, uid, role, branch)
    pa = await service.create_patient(
        owner, a, "Synthetic A", external_reference="A001", doctor_id="4"
    )
    pb = await service.create_patient(
        owner, b, "Synthetic B", external_reference="B001"
    )
    ca = await service.create_case(owner, pa["id"], "Callback A", "3")
    cb = await service.create_case(owner, pb["id"], "Callback B", "6")
    return {"owner": owner, "a": a, "b": b, "pa": pa, "pb": pb, "ca": ca, "cb": cb}
