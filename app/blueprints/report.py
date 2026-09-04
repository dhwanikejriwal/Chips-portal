from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, session, Response, jsonify
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
        
    from app.utils.backend_url import get_backend_base_url
    backend_url = f"{get_backend_base_url()}/api/reports/download/{report_id}"
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


@report_bp.route('/reports/delete/<int:report_id>', methods=['DELETE', 'POST'])
@report_bp.route('/delete/<int:report_id>', methods=['DELETE', 'POST'])
def delete_report_direct(report_id):
    from flask import Response, jsonify
    from app.utils.backend_url import get_backend_base_url
    backend_target = f"{get_backend_base_url()}/api/reports/{report_id}"
    raw_token = session.get("access_token", "")
    if isinstance(raw_token, dict):
        raw_token = raw_token.get("token", "") or raw_token.get("access_token", "")
    headers = {"Authorization": f"Bearer {str(raw_token).strip()}"} if raw_token else {}
    try:
        resp = requests.delete(backend_target, headers=headers, timeout=30)
        return Response(resp.content, status=resp.status_code, content_type=resp.headers.get("Content-Type", "application/json"))
    except Exception as e:
        return jsonify({"error": str(e), "detail": str(e)}), 500


@report_bp.route('/reports/proxy/<path:subpath>', methods=['GET', 'POST', 'PUT', 'DELETE'])
@report_bp.route('/proxy/<path:subpath>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def proxy_backend_report(subpath):
    from flask import Response, jsonify
    from app.utils.backend_url import get_backend_base_url
    backend_target = f"{get_backend_base_url()}/api/reports/{subpath}"
    
    raw_token = session.get("access_token", "")
    if isinstance(raw_token, dict):
        raw_token = raw_token.get("token", "") or raw_token.get("access_token", "")
    headers = {"Authorization": f"Bearer {str(raw_token).strip()}"} if raw_token else {}
    
    try:
        if request.method == 'POST':
            if request.files:
                files_payload = {}
                for k, v in request.files.items():
                    files_payload[k] = (v.filename, v.read(), v.content_type)
                resp = requests.post(
                    backend_target,
                    files=files_payload,
                    data=request.form,
                    headers=headers,
                    params=request.args,
                    timeout=120
                )
            else:
                json_data = request.get_json(silent=True)
                if json_data is not None:
                    resp = requests.post(backend_target, json=json_data, headers=headers, params=request.args, timeout=120)
                else:
                    resp = requests.post(backend_target, data=request.form, headers=headers, params=request.args, timeout=120)
        elif request.method == 'DELETE':
            resp = requests.delete(backend_target, headers=headers, params=request.args, timeout=30)
        elif request.method == 'PUT':
            resp = requests.put(backend_target, json=request.get_json(silent=True), headers=headers, params=request.args, timeout=60)
        else:
            resp = requests.get(backend_target, headers=headers, params=request.args, timeout=60)
            
        return Response(resp.content, status=resp.status_code, content_type=resp.headers.get("Content-Type", "application/json"))
    except Exception as e:
        return jsonify({"error": str(e), "detail": str(e)}), 500


@report_bp.route('/reports/sync-live', methods=['POST'])
def sync_live_data():
    role = session.get('role')
    if not role or role not in ['Admin', 'chips_admin']:
        return jsonify({"success": False, "message": "Unauthorized access. Admin privileges required."}), 403
    
    from app.utils.backend_url import get_backend_base_url
    backend_url = f"{get_backend_base_url()}/api/reports/sync/external"
    dry_run = request.args.get("dry_run", "false").lower() in ("true", "1")
    exact_mirror = request.args.get("exact_mirror", "true").lower() in ("true", "1")
    try:
        resp = requests.post(backend_url, params={"dry_run": dry_run, "exact_mirror": exact_mirror}, timeout=120)
        return Response(resp.content, status=resp.status_code, content_type=resp.headers.get("Content-Type", "application/json"))
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

