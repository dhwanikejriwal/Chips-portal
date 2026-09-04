from flask import Flask, render_template, request, redirect, url_for, session
from app.config import Config
import requests

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Serve static assets (CSS/JS) with revalidation instead of long-lived
    # browser caching, so edits to stylesheets/scripts show up on reload
    # without a hard refresh or per-file ?v= cache-buster.
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

    # Register blueprints (Friend's / Shared)
    from app.blueprints.auth import auth_bp
    from app.blueprints.dc_dashboard import dc_dashboard_bp
    from app.blueprints.chips_dashboard import chips_dashboard_bp
    from app.blueprints.candidate_register import candidate_register_bp
    from app.blueprints.selection import selection_bp
    from app.blueprints.candidate import candidate_bp
    from app.blueprints.lms_manage import lms_manage_bp
    from app.blueprints.nseit_manage import nseit_manage_bp
    from app.blueprints.monitoring import monitoring_bp
    from app.blueprints.l1_registration import l1_bp as l1_registration_bp
    from app.blueprints.reactivation import reactivation_bp
    from app.blueprints.l2_registration import l2_registration_bp
    from app.blueprints.operator_activation import operator_activation_bp
    from app.blueprints.station_id import station_id_bp
    from app.blueprints.operator_mapping import operator_mapping_bp
    from app.blueprints.operator_onboarding import operator_onboarding_bp
    from app.blueprints.report import report_bp
    from app.blueprints.operator_activity_dashboard import operator_activity_dashboard_bp
    from app.blueprints.operator_data import operator_data_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(dc_dashboard_bp, url_prefix="/auth")
    app.register_blueprint(chips_dashboard_bp, url_prefix="/auth")
    app.register_blueprint(candidate_register_bp, url_prefix="/auth")
    app.register_blueprint(selection_bp, url_prefix="/auth")
    app.register_blueprint(candidate_bp, url_prefix="/auth")
    app.register_blueprint(lms_manage_bp, url_prefix="/auth")
    app.register_blueprint(nseit_manage_bp, url_prefix="/auth")
    app.register_blueprint(monitoring_bp, url_prefix="/auth")
    app.register_blueprint(l1_registration_bp, url_prefix="/auth")
    app.register_blueprint(reactivation_bp, url_prefix="/auth")
    app.register_blueprint(l2_registration_bp, url_prefix="/auth")
    app.register_blueprint(operator_activation_bp, url_prefix="/auth")
    app.register_blueprint(station_id_bp, url_prefix="/auth")
    app.register_blueprint(operator_mapping_bp, url_prefix="/auth")
    app.register_blueprint(operator_onboarding_bp, url_prefix="/auth")
    app.register_blueprint(report_bp, url_prefix="/auth")
    app.register_blueprint(operator_activity_dashboard_bp, url_prefix="/auth")
    app.register_blueprint(operator_data_bp, url_prefix="/auth")

    @app.route("/reports/proxy/<path:subpath>", methods=["GET", "POST", "PUT", "DELETE"])
    def global_reports_proxy(subpath):
        from app.blueprints.report import proxy_backend_report
        return proxy_backend_report(subpath)

    @app.route("/reports/sync-live", methods=["POST"])
    def global_reports_sync_live():
        from app.blueprints.report import sync_live_data
        return sync_live_data()

    @app.route("/notifications/summary", methods=["GET"])
    def global_notifications_summary_proxy():
        from app.blueprints.auth import notification_summary_proxy
        return notification_summary_proxy()
    # Start periodic background temp file cleaner (purging files older than 1 hour)
    import os
    from app.utils.temp_cleaner import start_periodic_temp_cleaner
    temp_folder = os.path.join(app.root_path, "..", "uploads", "temp")
    start_periodic_temp_cleaner(temp_folder, max_age_seconds=3600, interval_seconds=900)

    @app.route("/")
    def index():
        from flask import render_template, current_app
        import requests
        
        activated_count = "4,200<span>+</span>"
        open_districts_count = 33
        open_districts = []
        try:
            backend_url = f"{current_app.config['BACKEND_API_URL']}/dashboard/stats"
            response = requests.get(backend_url, timeout=2)
            if response.status_code == 200:
                data = response.json()
                approved = data.get("summary", {}).get("approved", 0)
                if approved >= 0:
                    activated_count = f"{approved:,}"
                    
            dist_url = f"{current_app.config['BACKEND_API_URL']}/candidate_register/districts"
            dist_resp = requests.get(dist_url, timeout=2)
            if dist_resp.status_code == 200:
                districts_data = dist_resp.json()
                open_districts_count = len(districts_data)
                open_districts = districts_data
        except Exception:
            pass
        recently_opened_count = sum(1 for d in open_districts if d.get("is_recently_opened"))
        return render_template("home/home.html", activated_count=activated_count, open_districts_count=open_districts_count, open_districts=open_districts, recently_opened_count=recently_opened_count)
        
    @app.route("/open-districts")
    def open_districts_page():
        from flask import render_template, current_app
        import requests
        
        open_districts = []
        try:
            dist_url = f"{current_app.config['BACKEND_API_URL']}/candidate_register/districts"
            dist_resp = requests.get(dist_url, timeout=2)
            if dist_resp.status_code == 200:
                open_districts = dist_resp.json()
        except Exception:
            pass
            
        return render_template("home/open_districts.html", open_districts=open_districts)

    @app.route('/favicon.ico')
    def favicon():
        import os
        from flask import send_from_directory
        return send_from_directory(os.path.join(app.root_path, 'static', 'css', 'images'),
                                   'chips_logo.jpg', mimetype='image/jpeg')

    @app.route('/candidate_uploads/<path:filename>')
    def candidate_uploads(filename):
        import os
        from flask import send_from_directory
        return send_from_directory(os.path.join(app.root_path, '..', 'uploads', 'candidate'), filename)

    @app.route('/uploads/temp/<path:filename>')
    def temp_uploads(filename):
        import os
        from flask import send_from_directory
        return send_from_directory(os.path.join(app.root_path, '..', 'uploads', 'temp'), filename)

    # Load Hindi translations ONCE at startup and cache in memory.
    # Previously this was read + parsed + re-serialized on EVERY page request
    # (52KB file), which added unnecessary disk I/O on each render.
    import json as _json
    import os as _os
    _translations_path = _os.path.join(app.root_path, 'static', 'i18n', 'hi.json')
    _hindi_translations_str = "{}"
    if _os.path.exists(_translations_path):
        try:
            with open(_translations_path, 'r', encoding='utf-8') as _f:
                _hindi_translations_str = _json.dumps(
                    _json.load(_f), ensure_ascii=False
                )
        except Exception as _e:
            app.logger.error(f"Error loading hi.json: {_e}")

    @app.context_processor
    def inject_language_toggle():
        return {
            'ENABLE_LANGUAGE_TOGGLE': app.config.get('ENABLE_LANGUAGE_TOGGLE', True),
            'HINDI_TRANSLATIONS': _hindi_translations_str
        }

    return app
