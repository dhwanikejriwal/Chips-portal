from backend.models.base import Base, get_ist_time
from backend.models.lms import RequestStatus, CredentialRequest
from backend.models.noc import NocRequest
from backend.models.station import StationKitDetails
from backend.models.approvals import ApprovalHistory

from backend.models.master_user_role import MasterUserRole
from backend.models.master_status import MasterStatus
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
from backend.models.otp_verification import OtpVerification

__all__ = [
    "Base",
    "get_ist_time",
    "UserRole",
    "District",
    "User",
    "RequestStatus",
    "CredentialRequest",
    "NocRequest",
    "StationKitDetails",
    "ApprovalHistory",

    "MasterUserRole",
    "MasterStatus",
    "UserLogin",
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
    "L2RegistrationRequest",
    "L2RegistrationRemark",
    "OperatorActivationRequest",
    "ActivationDocument",
    "OperatorActivationRemark",
    "StationIDRequest",
    "StationIDRemark",
    "OtpVerification",
]
