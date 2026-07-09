"""initial full schema

Revision ID: 0001_initial_full_schema
Revises: 
Create Date: 2026-06-22

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0001_initial_full_schema'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # Tier 0 – No foreign-key dependencies                                #
    # ------------------------------------------------------------------ #

    op.create_table(
        'master_user_role',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False),
    )

    op.create_table(
        'district_table',
        sa.Column('district_code', sa.String(length=20), primary_key=True, nullable=False),
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('district_name', sa.String(length=100), nullable=False),
        sa.Column('district_short_name', sa.String(length=10), nullable=False),
    )

    # ------------------------------------------------------------------ #
    # Tier 1 – Depend only on Tier 0                                      #
    # ------------------------------------------------------------------ #

    op.create_table(
        'user_login_table',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('username', sa.String(length=100), nullable=False),
        sa.Column('password', sa.String(length=255), nullable=False),
        sa.Column('district_id', sa.String(length=20), nullable=True),
        sa.Column('roleid', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['district_id'], ['district_table.district_code']),
        sa.ForeignKeyConstraint(['roleid'], ['master_user_role.id']),
        sa.UniqueConstraint('username'),
    )
    op.create_index('ix_user_login_table_username', 'user_login_table', ['username'])

    op.create_table(
        'candidate_table',
        sa.Column('r_id', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('request_code', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('mobile', sa.String(length=15), nullable=False),
        sa.Column('email', sa.String(length=100), nullable=False),
        sa.Column('district', sa.String(length=20), nullable=False),
        sa.Column('qualification', sa.String(length=100), nullable=False),
        sa.Column('lms_id', sa.String(length=50), nullable=True),
        sa.Column('nseit_id', sa.String(length=50), nullable=True),
        sa.Column('exam_unique_code', sa.String(length=100), nullable=True),
        sa.Column('dob', sa.Date(), nullable=False),
        sa.Column('aadhaar', sa.String(length=12), nullable=False),
        sa.Column('address', sa.String(length=500), nullable=True),
        sa.Column('pincode', sa.String(length=10), nullable=True),
        sa.Column('is_existing_operator', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('photo_upload', sa.String(length=255), nullable=True),
        sa.Column('marksheet_upload', sa.String(length=255), nullable=True),
        sa.Column('tenth_marksheet_upload', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=True, server_default='Pending'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['district'], ['district_table.district_code']),
        sa.UniqueConstraint('request_code'),
    )
    op.create_index('ix_candidate_table_request_code', 'candidate_table', ['request_code'])

    # ------------------------------------------------------------------ #
    # Tier 2 – Depend on Tier 1                                           #
    # ------------------------------------------------------------------ #

    op.create_table(
        'candidate_login_table',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('r_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.String(length=100), nullable=False),
        sa.Column('password', sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(['r_id'], ['candidate_table.r_id']),
        sa.UniqueConstraint('r_id'),
        sa.UniqueConstraint('user_id'),
    )

    op.create_table(
        'dc_remark_table',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('r_id', sa.Integer(), nullable=False),
        sa.Column('remark', sa.String(length=1000), nullable=False),
        sa.Column('time', sa.DateTime(), nullable=False),
        sa.Column('status_after', sa.String(length=50), nullable=True),
        sa.Column('by', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['r_id'], ['candidate_table.r_id']),
        sa.ForeignKeyConstraint(['by'], ['user_login_table.id']),
    )

    op.create_table(
        'LMS_table',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('R_Id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=True, server_default='Pending'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['R_Id'], ['candidate_table.r_id']),
        sa.UniqueConstraint('R_Id'),
    )

    op.create_table(
        'nseit_request_table',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('R_Id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=True, server_default='Pending'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['R_Id'], ['candidate_table.r_id']),
        sa.UniqueConstraint('R_Id'),
    )

    op.create_table(
        'l1_registration_requests',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('request_code', sa.String(), nullable=False),
        sa.Column('district_id', sa.String(length=20), nullable=False),
        sa.Column('station_id', sa.String(), nullable=False),
        sa.Column('machine_id', sa.String(), nullable=False),
        sa.Column('operator_name', sa.String(), nullable=True),
        sa.Column('operator_id', sa.String(), nullable=True),
        sa.Column('model_type', sa.String(), nullable=False),
        sa.Column('software_version', sa.String(), nullable=False),
        sa.Column('uv_id', sa.String(), nullable=False),
        sa.Column('uv_password', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=True, server_default='PENDING'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['district_id'], ['district_table.district_code']),
        sa.UniqueConstraint('request_code'),
    )
    op.create_index('ix_l1_registration_requests_id', 'l1_registration_requests', ['id'])
    op.create_index('ix_l1_registration_requests_request_code', 'l1_registration_requests', ['request_code'])

    op.create_table(
        'operator_reactivation_requests',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('request_code', sa.String(length=50), nullable=False),
        sa.Column('dc_id', sa.Integer(), nullable=False),
        sa.Column('district_id', sa.String(length=20), nullable=False),
        sa.Column('operator_count', sa.Integer(), nullable=False),
        sa.Column('training_date', sa.Date(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='PENDING'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('reject_reason', sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(['dc_id'], ['user_login_table.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['district_id'], ['district_table.district_code'], ondelete='RESTRICT'),
        sa.UniqueConstraint('request_code'),
    )
    op.create_index('ix_operator_reactivation_requests_request_code', 'operator_reactivation_requests', ['request_code'])
    op.create_index('ix_operator_reactivation_requests_status', 'operator_reactivation_requests', ['status'])
    op.create_index('ix_operator_reactivation_requests_created_at', 'operator_reactivation_requests', ['created_at'])

    op.create_table(
        'l2_registration_requests',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('request_no', sa.String(length=20), nullable=True),
        sa.Column('dc_id', sa.Integer(), nullable=False),
        sa.Column('district_id', sa.String(length=20), nullable=True),
        sa.Column('client_version', sa.String(length=50), nullable=False),
        sa.Column('new_station_id', sa.String(length=50), nullable=False),
        sa.Column('ea_code', sa.String(length=50), nullable=False),
        sa.Column('reg_code', sa.String(length=50), nullable=False),
        sa.Column('new_machine_id', sa.String(length=50), nullable=False),
        sa.Column('client_type', sa.String(length=50), nullable=False),
        sa.Column('old_station_id', sa.String(length=50), nullable=True),
        sa.Column('reason_for_l2_registration', sa.Text(), nullable=True),
        sa.Column('old_machine_id', sa.String(length=50), nullable=True),
        sa.Column('tech_center_remarks', sa.Text(), nullable=True),
        sa.Column('operator_name', sa.String(length=100), nullable=False),
        sa.Column('operator_id', sa.String(length=50), nullable=False),
        sa.Column('unique_id', sa.String(length=50), nullable=True),
        sa.Column('block', sa.String(length=100), nullable=False),
        sa.Column('address_of_govt_premises', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='sent_to_chips'),
        sa.Column('uidai_remarks', sa.Text(), nullable=True),
        sa.Column('submitted_at', sa.DateTime(), nullable=False),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('reviewed_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['dc_id'], ['user_login_table.id']),
        sa.ForeignKeyConstraint(['district_id'], ['district_table.district_code']),
        sa.ForeignKeyConstraint(['reviewed_by'], ['user_login_table.id']),
        sa.UniqueConstraint('request_no'),
    )
    op.create_index('ix_l2_registration_requests_id', 'l2_registration_requests', ['id'])
    op.create_index('ix_l2_registration_requests_dc_id', 'l2_registration_requests', ['dc_id'])
    op.create_index('ix_l2_registration_requests_district_id', 'l2_registration_requests', ['district_id'])
    op.create_index('ix_l2_registration_requests_status', 'l2_registration_requests', ['status'])
    op.create_index('ix_l2_registration_requests_submitted_at', 'l2_registration_requests', ['submitted_at'])

    op.create_table(
        'operator_activation_requests',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('request_no', sa.String(length=20), nullable=True),
        sa.Column('dc_id', sa.Integer(), nullable=False),
        sa.Column('district_id', sa.String(length=20), nullable=True),
        sa.Column('role', sa.String(length=50), nullable=True),
        sa.Column('name_as_per_aadhaar', sa.String(length=120), nullable=False),
        sa.Column('registrar_code', sa.String(length=50), nullable=True),
        sa.Column('ea_code', sa.String(length=50), nullable=True),
        sa.Column('user_code', sa.String(length=50), nullable=True),
        sa.Column('nseit_certificate_number', sa.String(length=50), nullable=True),
        sa.Column('operator_mobile', sa.String(length=15), nullable=False),
        sa.Column('primary_email', sa.String(length=120), nullable=True),
        sa.Column('operator_aadhaar', sa.String(length=4), nullable=True),
        sa.Column('pan_number', sa.String(length=10), nullable=True),
        sa.Column('nseit_certification_date', sa.DateTime(), nullable=True),
        sa.Column('nseit_certificate_expiry_date', sa.DateTime(), nullable=True),
        sa.Column('pincode', sa.String(length=10), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='sent_to_chips'),
        sa.Column('remark_to_uidai', sa.Text(), nullable=True),
        sa.Column('submitted_at', sa.DateTime(), nullable=False),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('reviewed_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['dc_id'], ['user_login_table.id']),
        sa.ForeignKeyConstraint(['district_id'], ['district_table.district_code']),
        sa.ForeignKeyConstraint(['reviewed_by'], ['user_login_table.id']),
        sa.UniqueConstraint('request_no'),
    )
    op.create_index('ix_operator_activation_requests_id', 'operator_activation_requests', ['id'])
    op.create_index('ix_operator_activation_requests_dc_id', 'operator_activation_requests', ['dc_id'])
    op.create_index('ix_operator_activation_requests_district_id', 'operator_activation_requests', ['district_id'])
    op.create_index('ix_operator_activation_requests_status', 'operator_activation_requests', ['status'])
    op.create_index('ix_operator_activation_requests_submitted_at', 'operator_activation_requests', ['submitted_at'])
    op.create_index('ix_operator_activation_requests_reviewed_by', 'operator_activation_requests', ['reviewed_by'])

    op.create_table(
        'station_id_requests',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('request_no', sa.String(length=20), nullable=True),
        sa.Column('dc_id', sa.Integer(), nullable=False),
        sa.Column('district_id', sa.String(length=20), nullable=True),
        sa.Column('model', sa.String(length=10), nullable=False),
        sa.Column('user_type', sa.String(length=20), nullable=False),
        sa.Column('user_type_custom_reason', sa.Text(), nullable=True),
        sa.Column('number_of_kits', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='sent_to_chips'),
        sa.Column('station_id_inserted', sa.Text(), nullable=True),
        sa.Column('submitted_at', sa.DateTime(), nullable=False),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('reviewed_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['dc_id'], ['user_login_table.id']),
        sa.ForeignKeyConstraint(['district_id'], ['district_table.district_code']),
        sa.ForeignKeyConstraint(['reviewed_by'], ['user_login_table.id']),
        sa.UniqueConstraint('request_no'),
    )
    op.create_index('ix_station_id_requests_id', 'station_id_requests', ['id'])
    op.create_index('ix_station_id_requests_dc_id', 'station_id_requests', ['dc_id'])
    op.create_index('ix_station_id_requests_district_id', 'station_id_requests', ['district_id'])
    op.create_index('ix_station_id_requests_status', 'station_id_requests', ['status'])
    op.create_index('ix_station_id_requests_submitted_at', 'station_id_requests', ['submitted_at'])

    # ------------------------------------------------------------------ #
    # Tier 3 – Depend on Tier 2                                           #
    # ------------------------------------------------------------------ #

    op.create_table(
        'lms_remark_table',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('R_id', sa.Integer(), nullable=False),
        sa.Column('remark', sa.String(length=1000), nullable=False),
        sa.Column('time', sa.DateTime(), nullable=False),
        sa.Column('status_after', sa.String(length=50), nullable=True),
        sa.Column('admin_by_id', sa.Integer(), nullable=True),
        sa.Column('candidate_by_id', sa.Integer(), nullable=True),
        sa.Column('is_public', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(['R_id'], ['LMS_table.id']),
        sa.ForeignKeyConstraint(['admin_by_id'], ['user_login_table.id']),
        sa.ForeignKeyConstraint(['candidate_by_id'], ['candidate_login_table.id']),
    )

    op.create_table(
        'nseit_request_remark_table',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('R_Id', sa.Integer(), nullable=False),
        sa.Column('remark', sa.String(length=1000), nullable=False),
        sa.Column('time', sa.DateTime(), nullable=False),
        sa.Column('status_after', sa.String(length=50), nullable=True),
        sa.Column('admin_by_id', sa.Integer(), nullable=True),
        sa.Column('candidate_by_id', sa.Integer(), nullable=True),
        sa.Column('is_public', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(['R_Id'], ['nseit_request_table.id']),
        sa.ForeignKeyConstraint(['admin_by_id'], ['user_login_table.id']),
        sa.ForeignKeyConstraint(['candidate_by_id'], ['candidate_login_table.id']),
    )

    op.create_table(
        'l1_registration_remark_history',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('request_code', sa.String(), nullable=False),
        sa.Column('remark', sa.String(), nullable=False),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('user_role', sa.String(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['request_code'], ['l1_registration_requests.request_code'], ondelete='CASCADE'),
    )
    op.create_index('ix_l1_registration_remark_history_request_code', 'l1_registration_remark_history', ['request_code'])

    op.create_table(
        'reactivation_operators',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('request_code', sa.String(length=50), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=True),
        sa.Column('operator_name', sa.String(length=150), nullable=False),
        sa.Column('registrar_code', sa.String(length=50), nullable=True),
        sa.Column('ea_code', sa.String(length=50), nullable=True),
        sa.Column('user_code', sa.String(length=50), nullable=True),
        sa.Column('certificate_number', sa.String(length=100), nullable=True),
        sa.Column('lms_certificate_id', sa.String(length=100), nullable=True),
        sa.Column('operator_mobile', sa.String(length=20), nullable=False),
        sa.Column('email_id', sa.String(length=100), nullable=True),
        sa.Column('aadhaar_number', sa.String(length=20), nullable=True),
        sa.Column('certification_date', sa.Date(), nullable=True),
        sa.Column('remarks', sa.String(length=250), nullable=True),
        sa.Column('model_type', sa.String(length=50), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='PENDING'),
        sa.Column('reject_reason', sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(['request_code'], ['operator_reactivation_requests.request_code'], ondelete='CASCADE'),
    )
    op.create_index('ix_reactivation_operators_request_code', 'reactivation_operators', ['request_code'])

    op.create_table(
        'reactivation_remark_history',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('request_code', sa.String(length=50), nullable=False),
        sa.Column('remark_history', sa.Text(), nullable=False),
        sa.Column('sender_role', sa.String(length=50), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['request_code'], ['operator_reactivation_requests.request_code'], ondelete='CASCADE'),
    )
    op.create_index('ix_reactivation_remark_history_request_code', 'reactivation_remark_history', ['request_code'])

    op.create_table(
        'reactivation_documents',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('request_code', sa.String(length=50), nullable=False),
        sa.Column('doc_type', sa.String(length=100), nullable=False),
        sa.Column('path', sa.String(length=500), nullable=False),
        sa.Column('original_filename', sa.String(length=250), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['request_code'], ['operator_reactivation_requests.request_code'], ondelete='CASCADE'),
    )
    op.create_index('ix_reactivation_documents_request_code', 'reactivation_documents', ['request_code'])

    op.create_table(
        'l2_registration_remarks',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('request_id', sa.Integer(), nullable=False),
        sa.Column('author_id', sa.Integer(), nullable=False),
        sa.Column('author_role', sa.String(length=20), nullable=False),
        sa.Column('remark', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['request_id'], ['l2_registration_requests.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['author_id'], ['user_login_table.id']),
    )
    op.create_index('ix_l2_registration_remarks_id', 'l2_registration_remarks', ['id'])
    op.create_index('ix_l2_registration_remarks_request_id', 'l2_registration_remarks', ['request_id'])

    op.create_table(
        'activation_documents',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('request_id', sa.Integer(), nullable=False),
        sa.Column('doc_type', sa.String(length=40), nullable=False),
        sa.Column('file_path', sa.Text(), nullable=False),
        sa.Column('original_filename', sa.String(length=255), nullable=False),
        sa.Column('file_size_bytes', sa.Integer(), nullable=True),
        sa.Column('mime_type', sa.String(length=100), nullable=True),
        sa.Column('uploaded_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['request_id'], ['operator_activation_requests.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('request_id', 'doc_type', name='uq_activation_doc_request_doctype'),
    )
    op.create_index('ix_activation_documents_id', 'activation_documents', ['id'])
    op.create_index('ix_activation_documents_request_id', 'activation_documents', ['request_id'])

    op.create_table(
        'operator_activation_remarks',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('request_id', sa.Integer(), nullable=False),
        sa.Column('author_id', sa.Integer(), nullable=False),
        sa.Column('author_role', sa.String(length=20), nullable=False),
        sa.Column('remark', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['request_id'], ['operator_activation_requests.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['author_id'], ['user_login_table.id']),
    )
    op.create_index('ix_operator_activation_remarks_id', 'operator_activation_remarks', ['id'])
    op.create_index('ix_operator_activation_remarks_request_id', 'operator_activation_remarks', ['request_id'])

    op.create_table(
        'station_id_remarks',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('request_id', sa.Integer(), nullable=False),
        sa.Column('author_id', sa.Integer(), nullable=False),
        sa.Column('author_role', sa.String(length=20), nullable=False),
        sa.Column('remark', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['request_id'], ['station_id_requests.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['author_id'], ['user_login_table.id']),
    )
    op.create_index('ix_station_id_remarks_id', 'station_id_remarks', ['id'])
    op.create_index('ix_station_id_remarks_request_id', 'station_id_remarks', ['request_id'])


def downgrade() -> None:
    # Drop in reverse dependency order
    op.drop_table('station_id_remarks')
    op.drop_table('operator_activation_remarks')
    op.drop_table('activation_documents')
    op.drop_table('l2_registration_remarks')
    op.drop_table('reactivation_documents')
    op.drop_table('reactivation_remark_history')
    op.drop_table('reactivation_operators')
    op.drop_table('l1_registration_remark_history')
    op.drop_table('nseit_request_remark_table')
    op.drop_table('lms_remark_table')
    op.drop_table('station_id_requests')
    op.drop_table('operator_activation_requests')
    op.drop_table('l2_registration_requests')
    op.drop_table('operator_reactivation_requests')
    op.drop_table('l1_registration_requests')
    op.drop_table('nseit_request_table')
    op.drop_table('LMS_table')
    op.drop_table('dc_remark_table')
    op.drop_table('candidate_login_table')
    op.drop_table('candidate_table')
    op.drop_table('user_login_table')
    op.drop_table('district_table')
    op.drop_table('master_user_role')
