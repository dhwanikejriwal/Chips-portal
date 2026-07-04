from flask import Flask, render_template, request, redirect, url_for, session
from app.config import Config
import requests

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Register modular feature blueprints (Ours)
    from app.blueprints.noc import noc_bp
    from app.blueprints.station import station_bp
    from app.blueprints.approvals import approvals_bp
    from app.blueprints.lms import lms_bp

    app.register_blueprint(noc_bp)
    app.register_blueprint(station_bp)
    app.register_blueprint(approvals_bp)
    app.register_blueprint(lms_bp)

    # Register blueprints (Friend's / Shared)
    from app.blueprints.auth import auth_bp
    from app.blueprints.dashboard import dashboard_bp
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

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(dashboard_bp, url_prefix="/auth")
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

    @app.route("/")
    def index():
        from flask import render_template
        return render_template("home.html")

    return app
