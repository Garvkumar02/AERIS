import re

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Campus, User
from ..schemas import LoginRequest, LoginResponse, StudentRegistrationRequest
from ..core.security import hash_password, verify_password, create_access_token
from ..core.limiter import limiter
from ..config import settings

router = APIRouter(prefix="/auth", tags=["auth"])

def _login_response(user: User) -> LoginResponse:
    token = create_access_token(data={"sub": user.id, "role": user.role, "emp_id": user.employee_id})
    return LoginResponse(
        token=token,
        role=user.role,
        name=user.name,
        employee_id=user.employee_id,
        department=user.department,
        designation=getattr(user, "designation", None),
        user_id=user.id
    )

@router.post("/login", response_model=LoginResponse)
@limiter.limit(lambda: settings.RATE_LIMIT_LOGIN)
def login(
    request: Request,
    response: Response,
    req: LoginRequest,
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == req.email.strip()).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated"
        )

    return _login_response(user)

@router.post("/register", response_model=LoginResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(lambda: settings.RATE_LIMIT_LOGIN)
def register_student(
    request: Request,
    response: Response,
    req: StudentRegistrationRequest,
    db: Session = Depends(get_db),
):
    name = req.name.strip()
    employee_id = req.employee_id.strip()
    email = req.email.strip().lower()
    password_bytes = req.password.encode("utf-8")

    if len(name) < 2:
        raise HTTPException(status_code=400, detail="Enter your full name.")
    if not employee_id or len(employee_id) > 50:
        raise HTTPException(status_code=400, detail="Enter a valid student ID (up to 50 characters).")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(status_code=400, detail="Enter a valid email address.")
    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="Password must contain at least 8 characters.")
    if len(password_bytes) > 72:
        raise HTTPException(status_code=400, detail="Password must be 72 bytes or fewer.")

    if db.query(User).filter(
        (User.email == email) | (User.employee_id == employee_id)
    ).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That email or student ID is already registered."
        )

    campus = db.query(Campus).first()
    assigned_role = (getattr(req, "role", None) or "student").strip().lower()
    assigned_dept = getattr(req, "department", None) or "CSE"
    assigned_designation = getattr(req, "designation", None) or ("Student" if assigned_role == "student" else assigned_role.capitalize())
    assigned_status = getattr(req, "status", None) or "active"

    student = User(
        employee_id=employee_id,
        name=name,
        email=email,
        password_hash=hash_password(req.password),
        role=assigned_role,
        department=assigned_dept,
        designation=assigned_designation,
        status=assigned_status,
        campus_id=campus.id if campus else None,
    )
    db.add(student)
    try:
        db.commit()
        db.refresh(student)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That email or student ID is already registered."
        )

    return _login_response(student)
