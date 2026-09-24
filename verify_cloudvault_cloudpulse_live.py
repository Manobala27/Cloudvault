import os
import sys
import time
import uuid
import json
import urllib.request
from datetime import datetime, timezone

from app import create_app
from app.models import User
from app.services.cloudpulse_service import cloudpulse_service

def main():
    print("=" * 60)
    print("CLOUDVAULT -> CLOUDPULSE LIVE AWS END-TO-END VERIFICATION")
    print("=" * 60)

    app = create_app()
    with app.app_context():
        enabled, api_url, service_name, timeout = cloudpulse_service._get_config()
        print(f"Target Service Name: {service_name}")
        print(f"Target API Endpoint: {api_url}")
        print(f"Enabled: {enabled}")
        print("-" * 60)

        test_run_id = str(uuid.uuid4())[:8]
        print(f"Starting Test Run ID: {test_run_id}\n")

        # Mock / Test User
        test_user = User(id=9999, username=f"testuser_{test_run_id}", email=f"user_{test_run_id}@example.com")

        # 1. TEST 1: Successful Upload
        req_id_1 = f"e2e-upload-{test_run_id}"
        print(f"1. Sending FILE_UPLOAD (Success) [req_id={req_id_1}]...")
        res1 = cloudpulse_service.send_log(
            level="INFO",
            message=f"User '{test_user.username}' uploaded file 'quarterly_report_{test_run_id}.pdf' successfully (524288 bytes)",
            event="FILE_UPLOAD",
            user_id=test_user.id,
            file_name=f"quarterly_report_{test_run_id}.pdf",
            metadata={"test_run": test_run_id, "size": 524288},
            request_id=req_id_1
        )
        print(f"   Dispatched: {res1}")

        # 2. TEST 2: Failed Upload (Alert-worthy ERROR)
        req_id_2 = f"e2e-upload-fail-{test_run_id}"
        print(f"2. Sending FILE_UPLOAD (Failure) [req_id={req_id_2}]...")
        res2 = cloudpulse_service.send_log(
            level="ERROR",
            message=f"Failed to upload file 'massive_archive_{test_run_id}.zip' for user '{test_user.username}': S3 upload timeout",
            event="FILE_UPLOAD",
            user_id=test_user.id,
            file_name=f"massive_archive_{test_run_id}.zip",
            metadata={"test_run": test_run_id, "error": "S3 timeout"},
            request_id=req_id_2
        )
        print(f"   Dispatched: {res2}")

        # 3. TEST 3: Download
        req_id_3 = f"e2e-download-{test_run_id}"
        print(f"3. Sending FILE_DOWNLOAD [req_id={req_id_3}]...")
        res3 = cloudpulse_service.send_log(
            level="INFO",
            message=f"User '{test_user.username}' downloaded file 'quarterly_report_{test_run_id}.pdf'",
            event="FILE_DOWNLOAD",
            user_id=test_user.id,
            file_name=f"quarterly_report_{test_run_id}.pdf",
            metadata={"test_run": test_run_id},
            request_id=req_id_3
        )
        print(f"   Dispatched: {res3}")

        # 4. TEST 4: Delete
        req_id_4 = f"e2e-delete-{test_run_id}"
        print(f"4. Sending FILE_DELETE [req_id={req_id_4}]...")
        res4 = cloudpulse_service.send_log(
            level="INFO",
            message=f"User '{test_user.username}' moved file 'draft_{test_run_id}.docx' to trash",
            event="FILE_DELETE",
            user_id=test_user.id,
            file_name=f"draft_{test_run_id}.docx",
            metadata={"test_run": test_run_id},
            request_id=req_id_4
        )
        print(f"   Dispatched: {res4}")

        # 5. TEST 5: Share
        req_id_5 = f"e2e-share-{test_run_id}"
        print(f"5. Sending FILE_SHARE [req_id={req_id_5}]...")
        res5 = cloudpulse_service.send_log(
            level="INFO",
            message=f"User '{test_user.username}' created public share link for 'quarterly_report_{test_run_id}.pdf'",
            event="FILE_SHARE",
            user_id=test_user.id,
            file_name=f"quarterly_report_{test_run_id}.pdf",
            metadata={"test_run": test_run_id, "share_action": "create"},
            request_id=req_id_5
        )
        print(f"   Dispatched: {res5}")

        # 6. TEST 6: Login Success & Failure
        req_id_6a = f"e2e-login-succ-{test_run_id}"
        print(f"6a. Sending LOGIN_SUCCESS [req_id={req_id_6a}]...")
        res6a = cloudpulse_service.send_log(
            level="INFO",
            message=f"User '{test_user.username}' ({test_user.email}) logged in successfully via password",
            event="LOGIN_SUCCESS",
            user_id=test_user.id,
            metadata={"test_run": test_run_id, "auth_method": "password"},
            request_id=req_id_6a
        )
        print(f"   Dispatched: {res6a}")

        req_id_6b = f"e2e-login-fail-{test_run_id}"
        print(f"6b. Sending LOGIN_FAILURE [req_id={req_id_6b}]...")
        res6b = cloudpulse_service.send_log(
            level="WARNING",
            message=f"Failed login attempt for email '{test_user.email}' from 127.0.0.1 (attempts: 1, reason: invalid_password)",
            event="LOGIN_FAILURE",
            metadata={"test_run": test_run_id, "attempts": 1},
            request_id=req_id_6b
        )
        print(f"   Dispatched: {res6b}")

        # 7. TEST 7: File Restore
        req_id_7 = f"e2e-restore-{test_run_id}"
        print(f"7. Sending FILE_RESTORE [req_id={req_id_7}]...")
        res7 = cloudpulse_service.send_log(
            level="INFO",
            message=f"User '{test_user.username}' restored file 'draft_{test_run_id}.docx' from trash",
            event="FILE_RESTORE",
            user_id=test_user.id,
            file_name=f"draft_{test_run_id}.docx",
            metadata={"test_run": test_run_id},
            request_id=req_id_7
        )
        print(f"   Dispatched: {res7}")

        print("\n" + "=" * 60)
        print("AUTHENTICATING WITH CLOUDPULSE API GATEWAY...")
        print("=" * 60)

        login_req = urllib.request.Request(
            "https://c2064m9sol.execute-api.ap-south-1.amazonaws.com/dev/login",
            data=json.dumps({"username": "admin", "password": "password123"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(login_req, timeout=5) as login_resp:
            login_data = json.loads(login_resp.read().decode("utf-8"))
            token = login_data.get("token")
            print("  [OK] Authenticated with CloudPulse API. JWT Token obtained.")

        print("\n" + "=" * 60)
        print("WAITING FOR ASYNCHRONOUS AWS PIPELINE (SQS -> Lambda -> DynamoDB)...")
        print("=" * 60)

        expected_request_ids = {req_id_1, req_id_2, req_id_3, req_id_4, req_id_5, req_id_6a, req_id_6b, req_id_7}
        found_request_ids = set()

        for attempt in range(1, 6):
            print(f"Querying CloudPulse API endpoint '/logs/service/CloudVault' (Attempt {attempt}/5)...")
            time.sleep(3)

            query_req = urllib.request.Request(
                "https://c2064m9sol.execute-api.ap-south-1.amazonaws.com/dev/logs/service/CloudVault?limit=50",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}"
                },
                method="GET"
            )
            with urllib.request.urlopen(query_req, timeout=5) as query_resp:
                query_data = json.loads(query_resp.read().decode("utf-8"))
                retrieved_logs = query_data.get("logs", [])
                for log_item in retrieved_logs:
                    r_id = log_item.get("request_id")
                    if r_id in expected_request_ids:
                        found_request_ids.add(r_id)

            print(f"   Found {len(found_request_ids)} / {len(expected_request_ids)} test logs in CloudPulse.")
            if len(found_request_ids) == len(expected_request_ids):
                break

        print("\n" + "=" * 60)
        print("VERIFICATION SUMMARY:")
        print("=" * 60)
        all_passed = True
        for req_id in sorted(expected_request_ids):
            if req_id in found_request_ids:
                print(f"  [OK] {req_id} stored in CloudPulse DynamoDB and retrieved via API.")
            else:
                print(f"  [FAIL] {req_id} NOT found in CloudPulse.")
                all_passed = False

        print("=" * 60)
        if all_passed:
            print("ALL 8 REAL APPLICATION EVENT TYPES VERIFIED ON LIVE AWS CLOUDPULSE!")
        else:
            print("SOME EVENTS FAILED TO BE RETRIEVED.")
        print("=" * 60)

if __name__ == "__main__":
    main()
