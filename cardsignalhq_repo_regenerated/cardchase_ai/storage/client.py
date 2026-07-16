from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

import requests


class SupabaseError(RuntimeError):
    pass


@dataclass
class SupabaseStorage:
    url: str
    service_role_key: str
    timeout: int = 30

    def _headers(self, prefer: str | None = None) -> dict[str, str]:
        headers = {
            "apikey": self.service_role_key,
            "Authorization": f"Bearer {self.service_role_key}",
            "Content-Type": "application/json",
        }
        if prefer:
            headers["Prefer"] = prefer
        return headers

    def _auth_headers(self, user_token: str) -> dict[str, str]:
        return {
            "apikey": self.service_role_key,
            "Authorization": f"Bearer {user_token}",
            "Content-Type": "application/json",
        }

    def _get(self, table: str, params: dict[str, str]) -> list[dict[str, Any]]:
        endpoint = f"{self.url.rstrip('/')}/rest/v1/{table}"
        response = requests.get(endpoint, headers=self._headers(), params=params, timeout=self.timeout)
        if response.status_code >= 400:
            raise SupabaseError(f"Supabase select failed for {table}: {response.status_code} {response.text}")
        return response.json()

    def _get_as_user(self, table: str, params: dict[str, str], user_token: str) -> list[dict[str, Any]]:
        endpoint = f"{self.url.rstrip('/')}/rest/v1/{table}"
        response = requests.get(endpoint, headers=self._auth_headers(user_token), params=params, timeout=self.timeout)
        if response.status_code >= 400:
            raise SupabaseError(f"Supabase user select failed for {table}: {response.status_code} {response.text}")
        return response.json()

    def _post(self, table: str, payload: Any, prefer: str | None = None) -> list[dict[str, Any]]:
        endpoint = f"{self.url.rstrip('/')}/rest/v1/{table}"
        response = requests.post(endpoint, headers=self._headers(prefer), json=payload, timeout=self.timeout)
        if response.status_code >= 400:
            raise SupabaseError(f"Supabase insert failed for {table}: {response.status_code} {response.text}")
        if not response.text.strip():
            return []
        data = response.json()
        return data if isinstance(data, list) else [data]

    def _post_as_user(self, table: str, payload: Any, user_token: str, prefer: str | None = None) -> list[dict[str, Any]]:
        endpoint = f"{self.url.rstrip('/')}/rest/v1/{table}"
        headers = self._auth_headers(user_token)
        if prefer:
            headers["Prefer"] = prefer
        response = requests.post(endpoint, headers=headers, json=payload, timeout=self.timeout)
        if response.status_code >= 400:
            raise SupabaseError(f"Supabase user insert failed for {table}: {response.status_code} {response.text}")
        if not response.text.strip():
            return []
        data = response.json()
        return data if isinstance(data, list) else [data]

    def _patch_as_user(self, table: str, params: dict[str, str], payload: Any, user_token: str) -> list[dict[str, Any]]:
        endpoint = f"{self.url.rstrip('/')}/rest/v1/{table}"
        headers = self._auth_headers(user_token)
        headers["Prefer"] = "return=representation"
        response = requests.patch(endpoint, headers=headers, params=params, json=payload, timeout=self.timeout)
        if response.status_code >= 400:
            raise SupabaseError(f"Supabase user update failed for {table}: {response.status_code} {response.text}")
        if not response.text.strip():
            return []
        data = response.json()
        return data if isinstance(data, list) else [data]

    def _patch(self, table: str, params: dict[str, str], payload: Any, prefer: str | None = None) -> list[dict[str, Any]]:
        endpoint = f"{self.url.rstrip('/')}/rest/v1/{table}"
        headers = self._headers(prefer or "return=representation")
        response = requests.patch(endpoint, headers=headers, params=params, json=payload, timeout=self.timeout)
        if response.status_code >= 400:
            raise SupabaseError(f"Supabase update failed for {table}: {response.status_code} {response.text}")
        if not response.text.strip():
            return []
        data = response.json()
        return data if isinstance(data, list) else [data]

    def _delete_as_user(self, table: str, params: dict[str, str], user_token: str) -> None:
        endpoint = f"{self.url.rstrip('/')}/rest/v1/{table}"
        response = requests.delete(endpoint, headers=self._auth_headers(user_token), params=params, timeout=self.timeout)
        if response.status_code >= 400:
            raise SupabaseError(f"Supabase user delete failed for {table}: {response.status_code} {response.text}")

    def fetch_user(self, user_token: str) -> dict[str, Any]:
        endpoint = f"{self.url.rstrip('/')}/auth/v1/user"
        response = requests.get(endpoint, headers={"apikey": self.service_role_key, "Authorization": f"Bearer {user_token}"}, timeout=self.timeout)
        if response.status_code >= 400:
            raise SupabaseError(f"Supabase auth lookup failed: {response.status_code} {response.text}")
        return response.json()

    def upsert_players(self, player_names: Iterable[str]) -> None:
        rows = [{"name": name} for name in player_names]
        if rows:
            self._post("players", rows, prefer="resolution=merge-duplicates")

    def fetch_player_map(self, player_names: Iterable[str]) -> dict[str, str]:
        names = list(dict.fromkeys(player_names))
        if not names:
            return {}
        in_list = ",".join(f'"{name}"' for name in names)
        rows = self._get("players", {"select": "id,name", "name": f"in.({in_list})"})
        return {row["name"]: row["id"] for row in rows}

    def insert_pipeline_run(self, leaderboard_path: str, tracked_players: list[str], entry_count: int) -> int:
        rows = self._post(
            "pipeline_runs",
            {"leaderboard_path": leaderboard_path, "tracked_players": tracked_players, "entry_count": entry_count},
            prefer="return=representation",
        )
        return rows[0]["id"]

    def insert_leaderboard_entries(self, run_id: int, entries: list[dict[str, Any]], player_map: dict[str, str]) -> None:
        payload = []
        for rank, entry in enumerate(entries, start=1):
            player_name = entry["player_name"]
            payload.append(
                {
                    "run_id": run_id,
                    "player_id": player_map.get(player_name),
                    "player_name": player_name,
                    "rank": rank,
                    "performance_score": round(entry["hotness"]["performance_score"], 2),
                    "market_score": round(entry["hotness"]["market_score"], 2),
                    "total_score": round(entry["hotness"]["total_score"], 2),
                    "confidence_multiplier": round(entry["hotness"]["confidence_multiplier"], 2),
                    "tag": entry["hotness"]["tag"],
                    "reasons": entry["hotness"]["reasons"],
                    "stats_7d": entry["stats_7d"],
                    "stats_30d": entry["stats_30d"],
                    "market_snapshots": entry["market_snapshots"],
                }
            )
        if payload:
            self._post("leaderboard_entries", payload)

    def persist_leaderboard(self, leaderboard_path: str, entries: list[dict[str, Any]]) -> int:
        player_names = [entry["player_name"] for entry in entries]
        self.upsert_players(player_names)
        player_map = self.fetch_player_map(player_names)
        run_id = self.insert_pipeline_run(leaderboard_path, player_names, len(entries))
        self.insert_leaderboard_entries(run_id, entries, player_map)
        return run_id

    def fetch_latest_run(self) -> dict[str, Any] | None:
        rows = self._get("pipeline_runs", {"select": "id,created_at,leaderboard_path,tracked_players,entry_count", "order": "created_at.desc", "limit": "1"})
        return rows[0] if rows else None

    def mark_all_notifications_read(self, user_id: str, user_token: str) -> list[dict[str, Any]]:
        return self._patch_as_user(
            "notifications",
            {"user_id": f"eq.{user_id}", "read_at": "is.null"},
            {"read_at": datetime.now(timezone.utc).isoformat()},
            user_token,
        )

    def fetch_previous_run(self, exclude_run_id: int | None = None) -> dict[str, Any] | None:
        params = {"select": "id,created_at,leaderboard_path,tracked_players,entry_count", "order": "created_at.desc", "limit": "2"}
        rows = self._get("pipeline_runs", params)
        if not rows:
            return None
        if exclude_run_id is None:
            return rows[1] if len(rows) > 1 else None
        for row in rows:
            if int(row["id"]) != int(exclude_run_id):
                return row
        return None

    def fetch_run_leaderboard(self, run_id: int) -> list[dict[str, Any]]:
        rows = self._get(
            "leaderboard_entries",
            {
                "select": "player_name,player_id,rank,performance_score,market_score,total_score,confidence_multiplier,tag,reasons,stats_7d,stats_30d,market_snapshots",
                "run_id": f"eq.{run_id}",
                "order": "rank.asc",
            },
        )
        leaderboard = []
        for row in rows:
            leaderboard.append(
                {
                    "player_name": row["player_name"],
                    "player_id": row.get("player_id"),
                    "rank": row["rank"],
                    "stats_7d": row["stats_7d"],
                    "stats_30d": row["stats_30d"],
                    "market_snapshots": row["market_snapshots"],
                    "hotness": {
                        "performance_score": float(row["performance_score"]),
                        "market_score": float(row["market_score"]),
                        "total_score": float(row["total_score"]),
                        "confidence_multiplier": float(row["confidence_multiplier"]),
                        "tag": row["tag"],
                        "reasons": row["reasons"],
                    },
                }
            )
        return leaderboard

    def fetch_latest_leaderboard(self) -> list[dict[str, Any]]:
        latest_run = self.fetch_latest_run()
        if not latest_run:
            return []
        leaderboard = self.fetch_run_leaderboard(int(latest_run["id"]))
        for entry in leaderboard:
            entry["run"] = {"id": latest_run["id"], "created_at": latest_run["created_at"]}
        return leaderboard

    def fetch_player_latest(self, player_id: str) -> dict[str, Any] | None:
        latest_run = self.fetch_latest_run()
        if not latest_run:
            return None
        rows = self._get(
            "leaderboard_entries",
            {
                "select": "player_name,player_id,rank,performance_score,market_score,total_score,confidence_multiplier,tag,reasons,stats_7d,stats_30d,market_snapshots",
                "run_id": f"eq.{latest_run['id']}",
                "player_id": f"eq.{player_id}",
                "limit": "1",
            },
        )
        if not rows:
            return None
        row = rows[0]
        return {
            "player_name": row["player_name"],
            "player_id": row.get("player_id"),
            "stats_7d": row["stats_7d"],
            "stats_30d": row["stats_30d"],
            "market_snapshots": row["market_snapshots"],
            "hotness": {
                "performance_score": float(row["performance_score"]),
                "market_score": float(row["market_score"]),
                "total_score": float(row["total_score"]),
                "confidence_multiplier": float(row["confidence_multiplier"]),
                "tag": row["tag"],
                "reasons": row["reasons"],
            },
            "run": {"id": latest_run["id"], "created_at": latest_run["created_at"]},
        }


    def fetch_player_history(self, player_id: str, limit_runs: int = 14) -> list[dict[str, Any]]:
        rows = self._get(
            "leaderboard_entries",
            {
                "select": "created_at,run_id,player_name,player_id,rank,performance_score,market_score,total_score,confidence_multiplier,tag,stats_7d,stats_30d",
                "player_id": f"eq.{player_id}",
                "order": "created_at.desc",
                "limit": str(limit_runs),
            },
        )
        return [
            {
                "created_at": row["created_at"],
                "run_id": row["run_id"],
                "player_name": row["player_name"],
                "player_id": row.get("player_id"),
                "rank": row["rank"],
                "performance_score": float(row["performance_score"]),
                "market_score": float(row["market_score"]),
                "total_score": float(row["total_score"]),
                "confidence_multiplier": float(row["confidence_multiplier"]),
                "tag": row["tag"],
                "stats_7d": row["stats_7d"],
                "stats_30d": row["stats_30d"],
            }
            for row in rows
        ][::-1]

    def fetch_leaderboard_history(self, limit_runs: int = 10) -> list[dict[str, Any]]:
        runs = self._get("pipeline_runs", {"select": "id,created_at,entry_count", "order": "created_at.desc", "limit": str(limit_runs)})
        history = []
        for run in runs[::-1]:
            entries = self._get(
                "leaderboard_entries",
                {"select": "player_name,total_score,tag,rank", "run_id": f"eq.{run['id']}", "order": "rank.asc", "limit": "5"},
            )
            history.append({"run_id": run["id"], "created_at": run["created_at"], "entry_count": run["entry_count"], "leaders": entries})
        return history

    def fetch_admin_settings(self) -> dict[str, Any]:
        rows = self._get("admin_settings", {"select": "key,value", "order": "key.asc"})
        return {row["key"]: row.get("value") for row in rows}

    def upsert_admin_settings(self, settings_map: dict[str, Any]) -> list[dict[str, Any]]:
        payload = [{"key": k, "value": v} for k, v in settings_map.items()]
        return self._post("admin_settings", payload, prefer="resolution=merge-duplicates,return=representation")

    def fetch_tracked_players(self) -> list[dict[str, Any]]:
        rows = self._get("tracked_player_configs", {"select": "id,player_name,active,notes,created_at,updated_at", "order": "player_name.asc"})
        return rows

    def add_tracked_player(self, player_name: str, notes: str = "") -> dict[str, Any]:
        rows = self._post(
            "tracked_player_configs",
            {"player_name": player_name, "active": True, "notes": notes},
            prefer="resolution=merge-duplicates,return=representation",
        )
        return rows[0]

    def update_tracked_player(self, player_name: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        rows = self._patch("tracked_player_configs", {"player_name": f"eq.{player_name}"}, payload, prefer="return=representation")
        return rows[0] if rows else None

    def delete_tracked_player(self, player_name: str) -> None:
        endpoint = f"{self.url.rstrip('/')}/rest/v1/tracked_player_configs"
        response = requests.delete(endpoint, headers=self._headers(), params={"player_name": f"eq.{player_name}"}, timeout=self.timeout)
        if response.status_code >= 400:
            raise SupabaseError(f"Supabase delete failed for tracked_player_configs: {response.status_code} {response.text}")

    def fetch_user_watchlist(self, user_id: str, user_token: str) -> list[dict[str, Any]]:
        return self._get_as_user("watchlists", {"select": "id,player_id,player_name,created_at", "user_id": f"eq.{user_id}", "order": "created_at.desc"}, user_token)

    def add_user_watchlist_player(self, user_id: str, player_id: str | None, player_name: str, user_token: str) -> dict[str, Any]:
        rows = self._post_as_user(
            "watchlists",
            {"user_id": user_id, "player_id": player_id, "player_name": player_name},
            user_token,
            prefer="resolution=merge-duplicates,return=representation",
        )
        return rows[0] if rows else {"player_id": player_id, "player_name": player_name}

    def remove_user_watchlist_player(self, user_id: str, player_name: str, user_token: str) -> None:
        self._delete_as_user("watchlists", {"user_id": f"eq.{user_id}", "player_name": f"eq.{player_name}"}, user_token)

    def fetch_user_player_alert_rules(self, user_id: str, user_token: str) -> list[dict[str, Any]]:
        return self._get_as_user(
            "player_alert_rules",
            {
                "select": "id,user_id,player_name,min_hotness_delta,alert_on_hotness_jump,alert_on_buy_low,alert_on_most_chased,muted_until,created_at,updated_at",
                "user_id": f"eq.{user_id}",
                "order": "updated_at.desc",
            },
            user_token,
        )

    def upsert_user_player_alert_rule(self, user_id: str, player_name: str, payload: dict[str, Any], user_token: str) -> dict[str, Any]:
        rows = self._post_as_user(
            "player_alert_rules",
            {
                "user_id": user_id,
                "player_name": player_name,
                "min_hotness_delta": payload.get("min_hotness_delta", 8),
                "alert_on_hotness_jump": bool(payload.get("alert_on_hotness_jump", True)),
                "alert_on_buy_low": bool(payload.get("alert_on_buy_low", True)),
                "alert_on_most_chased": bool(payload.get("alert_on_most_chased", False)),
                "muted_until": payload.get("muted_until"),
            },
            user_token,
            prefer="resolution=merge-duplicates,return=representation",
        )
        return rows[0] if rows else {}

    def remove_user_player_alert_rule(self, user_id: str, player_name: str, user_token: str) -> None:
        self._delete_as_user("player_alert_rules", {"user_id": f"eq.{user_id}", "player_name": f"eq.{player_name}"}, user_token)


    def fetch_user_alert_subscription(self, user_id: str, user_token: str) -> dict[str, Any] | None:
        rows = self._get_as_user(
            "alert_subscriptions",
            {
                "select": "id,user_id,email,hotness_jump_enabled,buy_low_enabled,most_chased_enabled,daily_digest_enabled,updated_at",
                "user_id": f"eq.{user_id}",
                "limit": "1",
            },
            user_token,
        )
        return rows[0] if rows else None

    def upsert_user_alert_subscription(self, user_id: str, email: str | None, payload: dict[str, Any], user_token: str) -> dict[str, Any]:
        existing = self.fetch_user_alert_subscription(user_id, user_token)
        clean_payload = {
            "email": email,
            "hotness_jump_enabled": bool(payload.get("hotness_jump_enabled", True)),
            "buy_low_enabled": bool(payload.get("buy_low_enabled", True)),
            "most_chased_enabled": bool(payload.get("most_chased_enabled", False)),
            "daily_digest_enabled": bool(payload.get("daily_digest_enabled", True)),
        }
        if existing:
            rows = self._patch_as_user("alert_subscriptions", {"user_id": f"eq.{user_id}"}, clean_payload, user_token)
            return rows[0] if rows else existing
        rows = self._post_as_user("alert_subscriptions", {"user_id": user_id, **clean_payload}, user_token, prefer="return=representation")
        return rows[0]

    def fetch_alert_targets(self) -> list[dict[str, Any]]:
        return self._get(
            "alert_subscriptions",
            {
                "select": "user_id,email,hotness_jump_enabled,buy_low_enabled,most_chased_enabled,daily_digest_enabled,profiles(email),watchlists(player_id,player_name),player_alert_rules(player_name,min_hotness_delta,alert_on_hotness_jump,alert_on_buy_low,alert_on_most_chased,muted_until)",
                "order": "updated_at.desc",
            },
        )


    def fetch_recent_notifications(self, since_iso: str) -> list[dict[str, Any]]:
        return self._get(
            "notifications",
            {
                "select": "id,created_at,user_id,event_type,player_name,title,read_at",
                "created_at": f"gte.{since_iso}",
                "order": "created_at.desc",
            },
        )

    def insert_notifications(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not rows:
            return []
        return self._post("notifications", rows, prefer="return=representation")

    def mark_notification_delivery(self, notification_id: int, channel: str, status: str, destination: str | None = None, provider: str | None = None, provider_message_id: str | None = None, error: str | None = None) -> dict[str, Any]:
        rows = self._post(
            "notification_deliveries",
            {
                "notification_id": notification_id,
                "channel": channel,
                "status": status,
                "destination": destination,
                "provider": provider,
                "provider_message_id": provider_message_id,
                "error": error,
            },
            prefer="return=representation",
        )
        return rows[0] if rows else {}

    def fetch_user_notifications(self, user_id: str, user_token: str, limit: int = 50) -> list[dict[str, Any]]:
        return self._get_as_user(
            "notifications",
            {
                "select": "id,created_at,read_at,event_type,channel,title,message,player_id,player_name,metadata",
                "user_id": f"eq.{user_id}",
                "order": "created_at.desc",
                "limit": str(limit),
            },
            user_token,
        )

    def fetch_user_notification_summary(self, user_id: str, user_token: str) -> dict[str, int]:
        rows = self._get_as_user(
            "notifications",
            {
                "select": "id,read_at",
                "user_id": f"eq.{user_id}",
                "limit": "200",
                "order": "created_at.desc",
            },
            user_token,
        )
        unread_count = sum(1 for row in rows if not row.get("read_at"))
        return {"total": len(rows), "unread": unread_count}

    def mark_notification_read(self, user_id: str, notification_id: int, user_token: str) -> dict[str, Any] | None:
        rows = self._patch_as_user(
            "notifications",
            {"id": f"eq.{notification_id}", "user_id": f"eq.{user_id}"},
            {"read_at": datetime.now(timezone.utc).isoformat()},
            user_token,
        )
        return rows[0] if rows else None
