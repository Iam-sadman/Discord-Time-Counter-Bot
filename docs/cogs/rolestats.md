# 👥 Cog Documentation: `RoleStatsCog` (`cogs/rolestats.py`)

## 📌 Overview
The `RoleStatsCog` cog provides role-based voice audit and productivity reporting via the **`/rolestats`** command. It audits all non-bot members assigned to a specific role, separates active members from inactive members (0 seconds), generates an interactive paginated Discord embed, and automatically exports a detailed CSV attendance spreadsheet.

---

## 🏗️ Architecture & Data Pipeline
```mermaid
flowchart TD
    User[/rolestats <role> [start_date] [end_date]/] --> Auth{can_use_rolestats?}
    Auth -- Unauthorized --> Err[Access Denied]
    Auth -- Authorized --> Query[fetch_role_activity_data]
    
    Query --> Aggregate[Group by member: active vs. inactive]
    Aggregate --> View[RoleStatsView: Pagination & Filters]
    Aggregate --> CSV[generate_role_csv: In-memory StringIO]
    
    View --> Embed[build_embed: Medal ranking & audio breakdown]
    CSV --> File[discord.File: role_activity_report.csv]
    
    Embed --> Message[Discord Message with Attached CSV & Buttons]
    File --> Message
```

---

## ⚡ Slash Command Specification

### `/rolestats`
* **Description:** Check voice activity and generate a CSV report for members of a specific role.
* **Access Level:** Restricted to **Server Administrators** and roles defined in `.env` (`ROLESTATS_ALLOWED_ROLES` IDs or names).
* **Parameters:**
  * `role` *(Required, `discord.Role`)*: Target Discord role to audit (e.g. `@Labelers`, `@Checkers`, `@NightShift`).
  * `start_date` *(Optional, `str`)*: Start date in `YYYY-MM-DD` format (defaults to 1st of current month).
  * `end_date` *(Optional, `str`)*: End date in `YYYY-MM-DD` format (defaults to end of current month).

---

## 🎛️ Interactive UI Component: `RoleStatsView`

### 1. Filter Buttons (Row 0)
* **`🟢 Active (X)`**: Filters and ranks only members who logged $> 0$ seconds in voice.
* **`⚪ Inactive (Y)`**: Filters members with zero voice presence during the selected period for swift absenteeism auditing.
* **`👥 All (Z)`**: Lists the entire role membership roster.

### 2. Pagination Buttons (Row 1)
* **`◀ Prev`**: Navigates to the previous page of 10 workers.
* **`Page X/Y`**: Indicator button displaying current position.
* **`Next ▶`**: Navigates to the next page of 10 workers.

---

## 📄 Automated CSV Export (`generate_role_csv`)
Every `/rolestats` invocation automatically generates and attaches a ready-to-download CSV spreadsheet containing:
* `User ID`
* `Discord Username` / `Nickname`
* `Role Name`
* `Total Time (Formatted)` & `Total Seconds`
* `Unmuted Time` & `Unmuted Seconds`
* `Muted Time` & `Muted Seconds`
* `Deafened Time` & `Deafened Seconds`
* `Status` (`ACTIVE` vs `INACTIVE`)
* `Date Range`

---

## 🔒 Permission & Security Guardrails
* Verified by [`can_use_rolestats(member)`](file:///d:/Projects/Discord-Time-Counter-Bot/utils.py#L812):
  1. Grants access if `member.guild_permissions.administrator` is `True`.
  2. Compares member's roles against `ROLESTATS_ALLOWED_ROLES["ids"]` and `ROLESTATS_ALLOWED_ROLES["names"]`.
* In `interaction_check`, unauthorized members cannot interact with pagination buttons or change filter tabs.
