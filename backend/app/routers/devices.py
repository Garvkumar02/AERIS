from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import User, Device
from ..schemas import DeviceRegisterRequest, DeviceRegisterResponse
from ..core.security import get_current_user

router = APIRouter(prefix="/devices", tags=["devices"])

@router.post("/register", response_model=DeviceRegisterResponse)
def register_device(
    req: DeviceRegisterRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    device = db.query(Device).filter(
        Device.user_id == current_user.id,
        Device.device_id == req.device_id
    ).first()

    if not device:
        device = Device(
            user_id=current_user.id,
            device_id=req.device_id,
            platform=req.platform or "android",
            status="active",
            last_seen=datetime.utcnow()
        )
        db.add(device)
    else:
        device.last_seen = datetime.utcnow()
        device.status = "active"

    db.commit()
    return DeviceRegisterResponse(status="active")
