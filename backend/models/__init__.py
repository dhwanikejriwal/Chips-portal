from backend.models.base import Base
from backend.models.master_user_role import MasterUserRole
from backend.models.district import District
from backend.models.user_login import UserLogin, UserLogin as User
from backend.models.candidate import Candidate, CandidateLogin
from backend.models.dc_remark import DCRemark
from backend.models.lms import LMS, LMSRemark
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
from backend.models.aadhaar_district_resources import AadhaarDistrictResource
from backend.models.admin_login_logs import AdminLoginLog

__all__ = [
    "Base",
    "MasterUserRole",
    "District",
    "UserLogin",
    "User",
    "Candidate",
    "CandidateLogin",
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
    "AadhaarDistrictResource",
    "AdminLoginLog",
]
