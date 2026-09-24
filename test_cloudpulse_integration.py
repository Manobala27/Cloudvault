import os
import sys
import json
import unittest
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError, URLError

# Set test environment
os.environ["FLASK_ENV"] = "testing"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["CLOUDPULSE_ENABLED"] = "true"
os.environ["CLOUDPULSE_API_URL"] = "https://mock-cloudpulse.example.com/dev/logs"
os.environ["CLOUDPULSE_SERVICE_NAME"] = "CloudVault"
os.environ["CLOUDPULSE_TIMEOUT"] = "2.0"

from app import create_app, db
from app.models import User, File, Folder, Share, FileVersion
from app.services.cloudpulse_service import cloudpulse_service, CloudPulseService

class CloudPulseIntegrationTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    # ==========================================
    # TEST 1: Successful File Upload Log
    # ==========================================
    @patch('urllib.request.urlopen')
    def test_file_upload_success_log(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.status = 202
        mock_urlopen.return_value.__enter__.return_value = mock_response

        user = User(username='testuser', email='test@example.com', password='hashed_password')
        result = cloudpulse_service.log_upload(
            user=user,
            file_name='report.pdf',
            file_id=101,
            file_size=2048576,
            is_version=False,
            success=True,
            ip_address='192.168.1.50'
        )

        self.assertTrue(result)
        mock_urlopen.assert_called_once()
        req = mock_urlopen.call_args[0][0]
        self.assertEqual(req.get_method(), 'POST')
        self.assertEqual(req.headers.get('Content-type'), 'application/json')
        
        payload = json.loads(req.data.decode('utf-8'))
        self.assertEqual(payload['service'], 'CloudVault')
        self.assertEqual(payload['level'], 'INFO')
        self.assertEqual(payload['event'], 'FILE_UPLOAD')
        self.assertEqual(payload['file_name'], 'report.pdf')
        self.assertEqual(payload['file_id'], '101')
        self.assertIn("User 'testuser' uploaded file 'report.pdf' successfully", payload['message'])
        self.assertIn('timestamp', payload)
        self.assertIn('request_id', payload)

    # ==========================================
    # TEST 2: Failed File Upload Log
    # ==========================================
    @patch('urllib.request.urlopen')
    def test_file_upload_failure_log(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.status = 202
        mock_urlopen.return_value.__enter__.return_value = mock_response

        user = User(username='testuser', email='test@example.com', password='hashed_password')
        result = cloudpulse_service.log_upload(
            user=user,
            file_name='big_data.iso',
            file_size=104857600,
            success=False,
            error='Storage quota exceeded (100% full)',
            ip_address='192.168.1.50'
        )

        self.assertTrue(result)
        mock_urlopen.assert_called_once()
        req = mock_urlopen.call_args[0][0]
        payload = json.loads(req.data.decode('utf-8'))
        
        self.assertEqual(payload['service'], 'CloudVault')
        self.assertEqual(payload['level'], 'ERROR') # Alert-worthy level
        self.assertEqual(payload['event'], 'FILE_UPLOAD')
        self.assertEqual(payload['metadata']['success'], False)
        self.assertIn('Storage quota exceeded', payload['message'])

    # ==========================================
    # TEST 3: Download Log (Standard & Public)
    # ==========================================
    @patch('urllib.request.urlopen')
    def test_file_download_logs(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.status = 202
        mock_urlopen.return_value.__enter__.return_value = mock_response

        user = User(username='alice', email='alice@example.com', password='hashed_password')
        
        # Standard download
        res1 = cloudpulse_service.log_download(
            user=user,
            file_name='contract.docx',
            file_id=5,
            success=True,
            ip_address='10.0.0.1'
        )
        self.assertTrue(res1)
        req1 = mock_urlopen.call_args[0][0]
        payload1 = json.loads(req1.data.decode('utf-8'))
        self.assertEqual(payload1['level'], 'INFO')
        self.assertEqual(payload1['event'], 'FILE_DOWNLOAD')
        self.assertIn("User 'alice' downloaded file 'contract.docx'", payload1['message'])

        # Public download
        res2 = cloudpulse_service.log_download(
            user=user,
            file_name='public_sheet.csv',
            file_id=6,
            is_public=True,
            success=True,
            ip_address='10.0.0.2'
        )
        self.assertTrue(res2)
        req2 = mock_urlopen.call_args[0][0]
        payload2 = json.loads(req2.data.decode('utf-8'))
        self.assertEqual(payload2['event'], 'FILE_DOWNLOAD')
        self.assertEqual(payload2['metadata']['is_public'], True)

    # ==========================================
    # TEST 4: Delete Log (Soft and Permanent)
    # ==========================================
    @patch('urllib.request.urlopen')
    def test_file_delete_logs(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.status = 202
        mock_urlopen.return_value.__enter__.return_value = mock_response

        user = User(username='bob', email='bob@example.com', password='hashed_password')
        
        # Soft delete to trash
        cloudpulse_service.log_delete(user=user, file_name='old_notes.txt', file_id=12, permanent=False)
        req1 = mock_urlopen.call_args[0][0]
        p1 = json.loads(req1.data.decode('utf-8'))
        self.assertEqual(p1['level'], 'INFO')
        self.assertEqual(p1['event'], 'FILE_DELETE')
        self.assertIn('moved file \'old_notes.txt\' to trash', p1['message'])

        # Permanent delete
        cloudpulse_service.log_delete(user=user, file_name='old_notes.txt', file_id=12, permanent=True)
        req2 = mock_urlopen.call_args[0][0]
        p2 = json.loads(req2.data.decode('utf-8'))
        self.assertEqual(p2['level'], 'WARNING')
        self.assertEqual(p2['event'], 'FILE_DELETE')
        self.assertIn('permanently deleted file', p2['message'])

    # ==========================================
    # TEST 5: Share Log (Create, Revoke, Expire)
    # ==========================================
    @patch('urllib.request.urlopen')
    def test_file_share_logs(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.status = 202
        mock_urlopen.return_value.__enter__.return_value = mock_response

        user = User(username='carol', email='carol@example.com', password='hashed_password')
        
        # Create share
        cloudpulse_service.log_share(user=user, file_name='presentation.pptx', file_id=20, action='create', share_id=1)
        req1 = mock_urlopen.call_args[0][0]
        p1 = json.loads(req1.data.decode('utf-8'))
        self.assertEqual(p1['event'], 'FILE_SHARE')
        self.assertEqual(p1['level'], 'INFO')
        self.assertIn('created public share link', p1['message'])

        # Revoke share
        cloudpulse_service.log_share(user=user, file_name='presentation.pptx', file_id=20, action='revoke', share_id=1)
        req2 = mock_urlopen.call_args[0][0]
        p2 = json.loads(req2.data.decode('utf-8'))
        self.assertEqual(p2['event'], 'FILE_SHARE')
        self.assertIn('revoked share link', p2['message'])

    # ==========================================
    # TEST 6: Login Success & Login Failure Logs
    # ==========================================
    @patch('urllib.request.urlopen')
    def test_login_logs(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.status = 202
        mock_urlopen.return_value.__enter__.return_value = mock_response

        user = User(username='dave', email='dave@example.com', password='hashed_password')
        
        # Login success
        cloudpulse_service.log_login_success(user=user, ip_address='192.168.1.100', auth_method='password')
        req1 = mock_urlopen.call_args[0][0]
        p1 = json.loads(req1.data.decode('utf-8'))
        self.assertEqual(p1['event'], 'LOGIN_SUCCESS')
        self.assertEqual(p1['level'], 'INFO')
        self.assertIn("User 'dave' (dave@example.com) logged in successfully", p1['message'])

        # Single login failure (WARNING)
        cloudpulse_service.log_login_failure(email='dave@example.com', ip_address='192.168.1.100', attempts=1, reason='invalid_password')
        req2 = mock_urlopen.call_args[0][0]
        p2 = json.loads(req2.data.decode('utf-8'))
        self.assertEqual(p2['event'], 'LOGIN_FAILURE')
        self.assertEqual(p2['level'], 'WARNING')

        # Excessive login failures >= 5 (ERROR - triggers alert)
        cloudpulse_service.log_login_failure(email='dave@example.com', ip_address='192.168.1.100', attempts=5, reason='brute_force_suspected')
        req3 = mock_urlopen.call_args[0][0]
        p3 = json.loads(req3.data.decode('utf-8'))
        self.assertEqual(p3['event'], 'LOGIN_FAILURE')
        self.assertEqual(p3['level'], 'ERROR')

    # ==========================================
    # TEST 7: CloudPulse Unavailable Resiliency
    # ==========================================
    @patch('urllib.request.urlopen')
    def test_cloudpulse_unavailable_does_not_break_app(self, mock_urlopen):
        # Scenario A: Timeout
        mock_urlopen.side_effect = TimeoutError("Connection timed out")
        res_timeout = cloudpulse_service.send_log(level="INFO", message="Test timeout log")
        self.assertFalse(res_timeout)

        # Scenario B: Connection Refused / URLError
        mock_urlopen.side_effect = URLError("Connection refused")
        res_url = cloudpulse_service.send_log(level="INFO", message="Test conn refused log")
        self.assertFalse(res_url)

        # Scenario C: HTTP 500 Server Error
        mock_urlopen.side_effect = HTTPError("http://mock", 500, "Internal Server Error", {}, None)
        res_http = cloudpulse_service.send_log(level="INFO", message="Test server error")
        self.assertFalse(res_http)

        # Scenario D: CloudPulse Disabled
        with patch.dict(self.app.config, {'CLOUDPULSE_ENABLED': False}):
            res_disabled = cloudpulse_service.send_log(level="INFO", message="Disabled test")
            self.assertFalse(res_disabled)

    # ==========================================
    # TEST 8: File Version & Restore Logs
    # ==========================================
    @patch('urllib.request.urlopen')
    def test_file_restore_and_version_logs(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.status = 202
        mock_urlopen.return_value.__enter__.return_value = mock_response

        user = User(username='eva', email='eva@example.com', password='hashed_password')
        
        # Restore file
        cloudpulse_service.log_restore(user=user, file_name='archived.pdf', file_id=99, is_version=False)
        req1 = mock_urlopen.call_args[0][0]
        p1 = json.loads(req1.data.decode('utf-8'))
        self.assertEqual(p1['event'], 'FILE_RESTORE')
        self.assertIn('restored file \'archived.pdf\' from trash', p1['message'])

        # Restore version
        cloudpulse_service.log_restore(user=user, file_name='design.fig', file_id=100, is_version=True, version_num=3)
        req2 = mock_urlopen.call_args[0][0]
        p2 = json.loads(req2.data.decode('utf-8'))
        self.assertEqual(p2['event'], 'FILE_VERSION')
        self.assertIn('restored file \'design.fig\' to version V3', p2['message'])

if __name__ == '__main__':
    unittest.main()
