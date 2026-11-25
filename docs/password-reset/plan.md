# Plan: password resets without email

## Ask

Add a way to reset a password, including for the owner (who would otherwise be locked out of
the Admin tab too).

## Why no "Forgot password?" email

The app sends no email. Supabase's built-in sender only emails the project's team members and
allows a few emails an hour, so a self-service reset link would need custom SMTP (e.g. Resend)
plus the app URL in Supabase's allowed redirect URLs. That can be added later. Everything below
works with the service-role key the backend already has.

## Three ways in

1. **Owner resets someone** (Admin tab, whitelisted rows): **Reset password** → confirm →
   `POST /api/admin/users/{email}/reset-password` sets a random 12-character temporary password
   (Supabase admin `PUT /auth/v1/admin/users/{id}`) and returns it once. The owner copies it
   and sends it to the user. No email is sent.
2. **Anyone changes their own password** (top bar, **Change password**, accounts on only):
   `POST /api/account/password {current_password, new_password}`. The current password is
   checked with a password sign-in (that throwaway session is revoked), then the new one is set
   with the admin call. New passwords need 8+ characters, as at sign-up. The user stays signed in.
3. **Shell, for any account including the owner's:**
   `railway ssh -- python -m auth.access reset-password you@x.com` prints a new temporary
   password. It needs no sign-in, so it's the way back in when the owner forgets theirs. (The
   Supabase dashboard, Authentication → Users, also works.)

## Finding the account

The Supabase id comes from the access list (`user_id`, recorded when someone requests access).
Accounts without one (made in the Supabase dashboard, or the owner, who signs in without an
access-list entry) are looked up by email through `GET /auth/v1/admin/users`, page by page.
No account yet (e.g. an email pre-approved on the Admin tab that never signed up) → 404.

## Not done

Existing sessions aren't revoked on reset (Supabase's admin update doesn't, and removing the
email from the whitelist already cuts someone off at once). There's no forced "change your
temporary password" step after a reset.
