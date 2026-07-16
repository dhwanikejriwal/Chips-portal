from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, session
import requests

report_bp = Blueprint('report', __name__)

@report_bp.route('/reports', methods=['GET'])
def index():
    if session.get('role') not in ['Admin', 'chips_admin']:
        flash('Unauthorized access.', 'error')
        return redirect(url_for('auth.login'))
        
    history = []
    try:
        backend_url = f"{current_app.config['BACKEND_API_URL']}/reports/history"
        response = requests.get(backend_url, timeout=5)
        if response.status_code == 200:
            history = response.json()
    except Exception as e:
        print(f"Error fetching report history: {e}")
        
    return render_template('report/upload.html', history=history)

@report_bp.route('/reports/download/<int:report_id>', methods=['GET'])
def download(report_id):
    if session.get('role') not in ['Admin', 'chips_admin']:
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
