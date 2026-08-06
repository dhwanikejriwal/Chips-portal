from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, session
import requests

from backend.utils.district_mapper import get_division_for_district, is_lwe_district

report_bp = Blueprint('report', __name__)

@report_bp.route('/reports', methods=['GET'])
def index():
    role = session.get('role')
    if not role or role not in ['Admin', 'chips_admin', 'DC', 'EDM']:
        flash('Unauthorized access.', 'error')
        return redirect(url_for('auth.login'))
        
    history = []
    districts = []
    try:
        backend_url = f"{current_app.config['BACKEND_API_URL']}/reports/history"
        response = requests.get(backend_url, timeout=5)
        if response.status_code == 200:
            history = response.json()
            
        districts_url = f"{current_app.config['BACKEND_API_URL']}/candidate_register/districts?all_districts=true"
        dist_response = requests.get(districts_url, timeout=5)
        if dist_response.status_code == 200:
            districts = dist_response.json()
    except Exception as e:
        print(f"Error fetching report data: {e}")
        
    user_district = session.get('district_name') or session.get('district_id') or ''
    is_dc = role in ['DC', 'EDM']
    user_division = get_division_for_district(user_district) or ''
    is_lwe = is_lwe_district(user_district) == "Yes"
        
    return render_template('report/reports_dash.html', history=history, districts=districts, user_role=role, user_district=user_district, is_dc=is_dc, user_division=user_division, is_lwe=is_lwe)

@report_bp.route('/reports/download/<int:report_id>', methods=['GET'])
def download(report_id):
    role = session.get('role')
    if not role or role not in ['Admin', 'chips_admin', 'DC', 'EDM']:
        flash('Unauthorized access.', 'error')
        return redirect(url_for('auth.login'))
        
    backend_url = f"{current_app.config['BACKEND_API_URL']}/reports/download/{report_id}"
    try:
        response = requests.get(backend_url, stream=True)
        if response.status_code == 200:
            from flask import Response
            content_disposition = response.headers.get('Content-Disposition', f'attachment; filename="report_{report_id}.xlsx"')
            return Response(
                response.iter_content(chunk_size=1024),
                content_type=response.headers.get('Content-Type'),
                headers={'Content-Disposition': content_disposition}
            )
        else:
            flash('Error downloading report.', 'error')
            return redirect(url_for('report.index'))
    except Exception as e:
        flash('Error connecting to backend.', 'error')
        return redirect(url_for('report.index'))
