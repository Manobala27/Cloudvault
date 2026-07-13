import csv
import io
from flask import Blueprint, render_template, request, jsonify, make_response
from flask_login import login_required, current_user
from app.services.analytics_service import analytics_service
from app.models import ActivityLog
from app import db

analytics_bp = Blueprint('analytics', __name__, url_prefix='/analytics')

@analytics_bp.route('/', methods=['GET'])
@login_required
def dashboard():
    # Log analytics view
    log = ActivityLog(user_id=current_user.id, action='ANALYTICS_VIEWED', ip_address=request.remote_addr)
    db.session.add(log)
    db.session.commit()
    
    return render_template('analytics.html')

@analytics_bp.route('/data', methods=['GET'])
@login_required
def get_data():
    days_map = {'7': 7, '30': 30, '90': 90, '365': 365, 'all': None}
    days_param = request.args.get('days', '30')
    days = days_map.get(days_param, 30)
    
    data = analytics_service.get_user_analytics(current_user.id, days)
    return jsonify(data)

@analytics_bp.route('/export/csv', methods=['GET'])
@login_required
def export_csv():
    data = analytics_service.get_user_analytics(current_user.id, None)
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow(['Metric', 'Value'])
    writer.writerow(['Total Storage Used (Bytes)', data['storage_used']])
    writer.writerow(['Total Files', data['total_files']])
    writer.writerow(['Total Folders', data['total_folders']])
    writer.writerow(['Total Favorites', data['total_favorites']])
    writer.writerow(['Total Shares', data['total_shares']])
    writer.writerow(['Total File Versions', data['total_versions']])
    writer.writerow(['Files in Trash', data['trash_count']])
    writer.writerow(['Trash Size (Bytes)', data['trash_size']])
    if data['largest_file']:
        writer.writerow(['Largest File', data['largest_file']['name']])
    if data['smallest_file']:
        writer.writerow(['Smallest File', data['smallest_file']['name']])
        
    writer.writerow([])
    writer.writerow(['File Type', 'Count', 'Size (Bytes)'])
    for t in data['type_counts']:
        writer.writerow([t, data['type_counts'][t], data['type_sizes'][t]])
        
    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = "attachment; filename=analytics_export.csv"
    response.headers["Content-type"] = "text/csv"
    return response
