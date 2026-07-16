from backend.models.base import Base, get_ist_time
from backend.models.lms import LMS, LMSRemark

from backend.models.master_user_role import MasterUserRole
from backend.models.master_status import MasterStatus
from backend.models.district import District
from backend.models.user_login import UserLogin, UserLogin as User
from backend.models.user_profile import UserProfile
from backend.models.candidate import Candidate, CandidateLogin, CandidateDocument
from backend.models.dc_remark import DCRemark
from backend.models.hold_candidate import HoldCandidate
from backend.models.nseit import NSEITRequest, NSEITRemark
from backend.models.l1_registration import L1RegistrationRequest, L1RegistrationRemarkHistory
from backend.models.reactivation import (
    OperatorReactivationRequest,
    ReactivationOperator,
    ReactivationRemarkHistory,
    ReactivationDocument
)
from backend.models.l2_registration import L2RegistrationRequest, L2RegistrationRemark
from backend.models.operator_activation import (
    OperatorActivationRequest,
    ActivationDocument,
    OperatorActivationRemark,
)
from backend.models.station_id import StationIDRequest, StationIDRemark
from backend.models.otp_verification import OtpVerification
from backend.models.aadhaar_district_resources import AadhaarDistrictResource
from backend.models.admin_login_logs import AdminLoginLog

__all__ = [
    "Base",
    "get_ist_time",
    "District",
    "User",
    "MasterUserRole",
    "MasterStatus",
    "UserLogin",
    "Candidate",
    "CandidateLogin",
    "CandidateDocument",
    "DCRemark",
    "LMS",
    "LMSRemark",
    "NSEITRequest",
    "NSEITRemark",
    "L1RegistrationRequest",
    "L1RegistrationRemarkHistory",
    "OperatorReactivationRequest",
    "ReactivationOperator",
    "ReactivationRemarkHistory",
    "ReactivationDocument",
    "L2RegistrationRequest",
    "L2RegistrationRemark",
    "OperatorActivationRequest",
    "ActivationDocument",
    "OperatorActivationRemark",
    "StationIDRequest",
    "StationIDRemark",
    "OtpVerification",
    "AadhaarDistrictResource",
    "AdminLoginLog",
    "HoldCandidate",
]
