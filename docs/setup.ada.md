# Setting up Meeting Organizer
> Put your own copy of the app online, with its own new database, in about 20 minutes.

> Wording not translated yet is shown in English. To translate it, see [docs/translating.md](translating.md).

> Wording not translated yet is shown in English. To translate it, see [docs/translating.md](translating.md).

[English](setup.en.md)

## Before you start
- A **GitHub** account that can see the `meeting-organizer` repository.
- A **Neon** account (neon.tech, the free plan is enough). The app gets a brand-new Neon project of its own: never
reuse the database of another app.
- A **Vercel** account (vercel.com, the free plan is enough), signed in with GitHub.
- A password you will use to sign in to the app.
- For printing on the official forms: the blank S-89 (PDF) and S-140 (Word) in English and/or Dangme, and the

current Life and Ministry Meeting Workbook PDF.

## Steps
1. **Make the database.** In Neon, choose **New project**. Give it a name such as `meeting-organizer` and pick the
region closest to you. Leave the other choices as they are and create it.
2. **Copy its address.** On the project's dashboard, choose **Connect**. Make sure **Connection pooling** is on and
copy the connection string. It starts with `postgresql://` and has `-pooler` in the host name.
3. **Make a secret.** You need a long random string for signing the sign-in cookie. Any password generator works:
ask it for 40 letters and digits.
4. **Create the Vercel project.** In Vercel, choose **Add New… → Project**, find `meeting-organizer` and choose
**Import**. Vercel recognises it as Next.js; leave the build settings as they are.

5. **Add the three settings.** Before deploying, open **Environment Variables** and add:
   |---|---|
| Name | Value |
| `DATABASE_URL` | the connection string from step 2 |
| `SESSION_SECRET` | the random string from step 3 |

| `APP_PASSWORD` | the password you will sign in with |
6. **Deploy.** Choose **Deploy**. The build creates the app's tables in the new database (empty: no people, no
meetings), then publishes the app. It takes two or three minutes.
7. **Sign in.** Open the address Vercel shows (ending in `.vercel.app`) and sign in with your password.
8. **Choose your languages.** In the side menu (on a phone: **More**), choose the **App language** for the screens
and the **Slip language** for everything printed. Each can be English or Dangme, and they can differ.
9. **Fill in Admin → Settings.** Your congregation's name, your own name (used for the greeting on Home), the
meeting day and time, and whether you use an auxiliary classroom.
10. **Upload the blank forms.** Under **Admin**, upload the S-89 PDF and the S-140 Word file for each language you
print in. The app checks each file and says how many slips or weeks it holds.
11. **Add the participants.** Under **Participants**, add each person with their privileges, family and any groups.
12. **Upload the workbook.** Under **Workbook PDF**, upload the current workbook (English or Dangme). The weeks and

their parts appear on **Create or edit**.

### Nightly backup (optional, recommended)
1. In Neon, choose **Connect** again, turn **Connection pooling** off and copy that (direct) connection string.
2. In GitHub, open the repository's **Settings → Secrets and variables → Actions → New repository secret**. Name it
`BACKUP_DATABASE_URL` and paste the string.
3. Every night a full copy of the database is saved under **Actions → Nightly backup**, kept for 30 days. You can

also download a backup file at any time under **Admin → Data & backup**.

## Check it worked
- Home greets you by name and shows the next midweek meeting.
- **Create or edit** lists the workbook's parts for the week, and **Suggest** fills them from your participants.
- **Slips and printing** offers slips on the official S-89 and an S-140 for the month, in the slip language.

- Opening `/api/py?op=ping` while signed in shows `"ok": true` and how long the database took to answer.

## If something goes wrong
- **The build fails with “couldn't set up the database”.** `DATABASE_URL` is wrong or the Neon project is paused.
Copy the connection string again (step 2), update it under Vercel → Settings → Environment Variables, and
redeploy.
- **The sign-in page says sign-in isn't set up yet.** `APP_PASSWORD` is missing. Add it and redeploy.
- **“SESSION_SECRET is not set”.** Add it (at least 16 characters, 40 is better) and redeploy. Changing it later
signs you out and retires every calendar link sent to participants.
- **Slips say no blank S-89 has been uploaded.** Upload it under Admin for the slip language you chose.
- **The workbook shows weeks with missing parts.** Check the workbook is the Life and Ministry Meeting Workbook PDF
itself, not a scan or a photo. Parts can be corrected by hand on the Workbook PDF page.
- **Five wrong passwords.** Sign-in is locked for a minute. Wait, then try again.
- **Vercel deploys from an unexpected branch.** The repository started out empty, so its first branch became the
default branch. Under Vercel → Settings → Git you can choose which branch is Production.
