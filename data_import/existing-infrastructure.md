# Existing data infrastructure

As mentioned, BGA [has an automated rig](https://github.com/mattkiefer/gm) for
sending FOIA requests and filing responses.

## How it works

Everything is pretty much undocumented, but here's what I can glean from
[the apparent controller](https://github.com/mattkiefer/gm/blob/master/mgr.py).

### Initialization tasks

- `init_contacts` – [Create Gmail contacts](https://github.com/mattkiefer/gm/blob/master/contacts/contacts.py#L18-L32)
  for each agency from existing CSV containing `first_name`, `last_name`,
  `agency`, and `email`
  - This CSV does not live in the repo, but presumably we can get our hands on it
- `init_labels` – [Create Gmail labels](https://github.com/mattkiefer/gm/blob/master/msg/label.py#L171-L177)
  for each agency and pre-defined statuses
  - `unidentified`
  - `responded`
  - `attachment`
  - `done`
- `init_msgs` – [Draft and send](https://github.com/mattkiefer/gm/blob/master/msg/compose.py#L23-L35)
  a [form FOIA](https://github.com/mattkiefer/gm/blob/master/msg/payroll-foia2017.docx) 
  to each agency

### Ongoing tasks

- `cron_label` – [Add labels](https://github.com/mattkiefer/gm/blob/master/msg/label.py#L24-L30)
  to unlabeled messages
- `cron_att` – Create agency folder and [stash response documents](https://github.com/mattkiefer/gm/blob/master/att/gm.py#L14-L32)
  in Google Drive
- `cron_report` – Generate per-agency [status report](https://github.com/mattkiefer/gm/blob/master/report/response.py#L22-L26)
  - In addition to the above labels, an agency can have also a status of `sent`
    or `shipped`. It's unclear how `shipped` is different than `done` (perhaps
    `done` is not yet in the Drive), but `shipped` supercedes it.
