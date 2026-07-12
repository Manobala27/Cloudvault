# Testing Checklist

Use this checklist to manually verify the full functionality and security of the CloudVault application.

## 1. Authentication & Security
- [ ] **Registration Validation:** Attempt to register with a password that is less than 8 characters or missing uppercase/lowercase/numbers/special characters. Verify it is rejected with the correct message.
- [ ] **Rate Limiting:** Refresh the `/login` or `/register` page rapidly more than 10 times. Verify you receive the custom `429 Too Many Requests` page.
- [ ] **Secure Login:** Log in with correct credentials. Verify you are redirected to the Dashboard.
- [ ] **Access Control:** Try to access `/dashboard` or `/upload` while logged out. Verify you are redirected to the login page.
- [ ] **Session Logout:** Log out and verify session data is cleared (cannot use back button to view cached private data).

## 2. File Upload (Module 4)
- [ ] **Invalid File Type:** Attempt to upload an executable (`.exe`) or unsupported format. Verify rejection.
- [ ] **Oversized File:** Attempt to upload a file larger than 10MB. Verify rejection and error message.
- [ ] **Successful Upload:** Upload a valid image (`.jpg`). Verify the UI loading spinner appears and button is disabled. Verify redirection to Dashboard on success.
- [ ] **Database Verification:** Check `site.db` (or the Dashboard) to ensure the file record was created.
- [ ] **S3 Verification:** Check the AWS S3 console to ensure the file was uploaded into `user_<id>/`.

## 3. Storage Dashboard (Module 5)
- [ ] **Thumbnail Loading:** Verify images display a preview thumbnail.
- [ ] **Statistics:** Verify "Total Files" and "Storage Used" update accurately based on your uploads.
- [ ] **Searching:** Type a filename in the search box and verify the table filters correctly.
- [ ] **Sorting:** Change the dropdown to "Oldest", "Name (A-Z)", etc., and verify the table reorders correctly.
- [ ] **Pagination:** (Optional) Upload 11 small files and verify pagination controls appear and work.

## 4. Advanced Secure File Sharing (Module 12)
- [ ] **Generate Link with Limits:** Click `Share` on an unshared file, set an expiration of 1 Day, a download limit of 1, and create the link. Verify the UI updates to show it is shared.
- [ ] **Public Password Prompt:** Create a share link with a password. Copy the public link, open an Incognito Window, and verify it prompts for a password (`shared_password.html`).
- [ ] **Enforce Password:** Enter an incorrect password. Verify you receive a failure message. Enter the correct password and verify you reach the secure download page.
- [ ] **Enforce Download Limit:** Click "Secure Download" on the limited share link. It should download successfully. Refresh the page or try to download again. Verify the link is immediately disabled (returns an error) since it reached its 1-download limit.
- [ ] **Shares Dashboard:** Go to the "Shared Files" tab in the main navigation. Verify your active and inactive links appear in the table with correct metadata (Limits, Expiry, Status).
- [ ] **Revoke Link:** From the "Shared Files" dashboard, click "Revoke" on an active share. Verify the status changes to Inactive and the link no longer works.

## 5. File Actions
- [ ] **Preview:** Click the `Preview` button for an image. Verify it opens securely in a new tab without downloading instantly.
- [ ] **Download:** Click the `Download` button. Verify it immediately triggers a file download attachment with the correct original filename.
- [ ] **Copy URL:** Click `Copy URL`, paste it into an incognito window, and verify it loads the file. Wait 1 hour (if testing expiration) to ensure it expires.
- [ ] **Deletion:** Click `Delete`, cancel the modal (verify it does not delete), then click `Delete` and confirm. Verify it is removed from the UI, the Database, and the AWS S3 Bucket.

## 6. Logical Folders (Module 8)
- [ ] **Create Folder:** Create a new folder named "Taxes". Verify it appears in the dashboard.
- [ ] **Navigate:** Click the folder to navigate inside. Verify the breadcrumbs read "Home / Taxes".
- [ ] **Contextual Upload:** Upload a file while inside the folder. Verify the file appears inside the folder and not in Home.
- [ ] **Cascading Deletion (Soft Delete):** Delete a folder. Verify the folder and all nested files are moved to the Trash.

## 7. Trash / Recycle Bin (Module 9)
- [ ] **Soft Delete:** Delete a file from the Dashboard. Verify it disappears from the Dashboard and appears in the Trash.
- [ ] **Secure Trash Share:** Attempt to visit the public share link of a deleted file. Verify it returns a 404 Not Found error.
- [ ] **Restore File:** Go to the Trash and restore a file. Verify it returns to its original folder in the Dashboard.
- [ ] **Restore Orphaned File:** Soft delete a folder containing a file. Delete the folder permanently from Trash. Then try to restore the file from Trash. Verify it is safely restored to the Home directory.
- [ ] **Permanent Deletion:** Permanently delete a file from the Trash. Verify the confirmation modal appears, and upon confirmation, check AWS S3 to ensure the object was permanently deleted.

## 8. Activity Log / Audit History (Module 11)
- [ ] **Authentication Tracking:** Log out and log back in. Navigate to the Activity page and verify `LOGOUT` and `LOGIN` events are listed with your IP address.
- [ ] **File Operations:** Upload a file and download it. Check the Activity log to see `UPLOAD` and `DOWNLOAD` recorded alongside the exact file name.
- [ ] **Share Operations:** Share a file and then revoke the share link. Check the Activity log for `SHARE` and `REVOKE_SHARE`.
- [ ] **Trash Operations:** Soft delete, restore, and permanently delete a file. Ensure all 3 events are accurately logged.
- [ ] **Filters & Search:** Use the dropdown filter on the Activity page to show only "UPLOAD" actions. Then use the search bar to find a specific file by name.

## 9. Global Error Handling
- [ ] **404 Page:** Navigate to `http://127.0.0.1:5000/does-not-exist`. Verify the custom 404 page is displayed.
- [ ] **Logging:** Check `logs/cloudvault.log` to ensure startup events are being recorded cleanly without dumping sensitive credentials.
