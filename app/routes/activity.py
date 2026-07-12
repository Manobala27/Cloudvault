from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from app.models import ActivityLog

activity_bp = Blueprint('activity', __name__)

@activity_bp.route('/activity')
@login_required
def index():
    page = request.args.get('page', 1, type=int)
    action_filter = request.args.get('action', '')
    search_query = request.args.get('search', '')

    query = ActivityLog.query.filter_by(user_id=current_user.id)

    if action_filter:
        query = query.filter_by(action=action_filter)
        
    if search_query:
        query = query.filter(
            (ActivityLog.file_name.ilike(f'%{search_query}%')) |
            (ActivityLog.folder_name.ilike(f'%{search_query}%'))
        )

    # Latest activities first
    query = query.order_by(ActivityLog.created_at.desc())

    # Pagination: 20 per page
    activities = query.paginate(page=page, per_page=20)

    # Get distinct actions for the filter dropdown
    distinct_actions = [r[0] for r in ActivityLog.query.with_entities(ActivityLog.action).distinct().all()]

    return render_template('activity.html', 
                           title='Activity Log', 
                           activities=activities, 
                           action_filter=action_filter,
                           search_query=search_query,
                           distinct_actions=distinct_actions)
