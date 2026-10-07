# 📑 Cog Documentation: `ReportCog` (`cogs/report.py`)

## 📌 Overview
The `ReportCog` cog provides on-demand, manual server-wide attendance reporting through the **`/report`** slash command. It triggers full server voice activity CSV aggregation for the active calendar month.

---

## ⚡ Slash Command Specification

### `/report`
* **Description:** Manually generate the current month's voice report CSV.
* **Access Level:** Server Members (restricted to `STATS_CHANNEL_ID` if configured in `.env`).
* **Parameters:** *None.*
* **Behavior:**
  1. Validates channel restriction against `STATS_CHANNEL_ID`.
  2. Defers response to handle database aggregation.
  3. Invokes [`generate_and_send_csv(interaction, "this_month")`](file:///d:/Projects/Discord-Time-Counter-Bot/utils.py#L650).
  4. Generates an in-memory CSV containing all tracked members, audio state breakdown, and primary channels.
  5. Sends the CSV file along with a formatted summary embed into the channel.

---

## 📊 CSV Export Schema
The generated spreadsheet (`voice_report_YYYY-MM.csv`) includes:
* `User ID`
* `User Name`
* `Total Time (Formatted)` & `Total Seconds`
* `Unmuted Time (Formatted)` & `Unmuted Seconds`
* `Muted Time (Formatted)` & `Muted Seconds`
* `Deafened Time (Formatted)` & `Deafened Seconds`
* `Top Channel`
* `Active Days Count`
