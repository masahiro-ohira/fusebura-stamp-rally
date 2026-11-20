function jsonResponse(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "Content-Type": "application/json; charset=UTF-8",
      "Cache-Control": "no-store",
    },
  });
}

async function getHistory(db, participantId) {
  const result = await db
    .prepare(`
      SELECT
        stamps.id,
        stamps.spot_id,
        spots.type,
        spots.name,
        stamps.acquired_at,
        stamps.scan_order
      FROM stamps
      JOIN spots ON spots.id = stamps.spot_id
      WHERE stamps.participant_id = ?
      ORDER BY stamps.scan_order ASC, stamps.id ASC
    `)
    .bind(participantId)
    .all();

  return result.results || [];
}

export async function onRequest(context) {
  const { request, env } = context;

  try {
    if (!env.DB) {
      return jsonResponse(
        {
          ok: false,
          error: "D1 database binding DB is not available.",
        },
        500
      );
    }

    const url = new URL(request.url);

    // 履歴取得
    if (request.method === "GET") {
      const participantId = url.searchParams.get("participantId");

      if (!participantId) {
        return jsonResponse(
          {
            ok: false,
            error: "participantId is required.",
          },
          400
        );
      }

      const history = await getHistory(env.DB, participantId);

      return jsonResponse({
        ok: true,
        participantId,
        history,
      });
    }

    // スタンプ取得
    if (request.method === "POST") {
      let body;

      try {
        body = await request.json();
      } catch {
        return jsonResponse(
          {
            ok: false,
            error: "Invalid JSON.",
          },
          400
        );
      }

      if (!body || typeof body !== "object" || Array.isArray(body)) {
        return jsonResponse({ ok: false, error: "Invalid request body." }, 400);
      }

      const action = body.action || "stamp";

      if (action === "reset") {
        return jsonResponse({
          ok: false,
          code: "RESET_DISABLED",
          message: "公開APIからの履歴削除は利用できません。",
        }, 403);
      }

      if (action !== "stamp") {
        return jsonResponse({ ok: false, error: "Unknown action." }, 400);
      }

      const spotId = String(body.spotId || "").trim();

      if (!spotId) {
        return jsonResponse(
          {
            ok: false,
            error: "spotId is required.",
          },
          400
        );
      }

      const spot = await env.DB
        .prepare(`
          SELECT id, type, name, active
          FROM spots
          WHERE id = ?
        `)
        .bind(spotId)
        .first();

      if (!spot) {
        return jsonResponse(
          {
            ok: false,
            error: "Spot not found.",
          },
          404
        );
      }

      if (Number(spot.active) !== 1) {
        return jsonResponse(
          {
            ok: false,
            error: "This spot is currently inactive.",
          },
          403
        );
      }

      let participantId = String(body.participantId || "").trim();

      if (!participantId) {
        participantId = crypto.randomUUID();
      }

      // 参加者を登録
      await env.DB
        .prepare(`
          INSERT OR IGNORE INTO participants (id)
          VALUES (?)
        `)
        .bind(participantId)
        .run();

      await env.DB
        .prepare(`
          UPDATE participants
          SET last_seen_at = CURRENT_TIMESTAMP
          WHERE id = ?
        `)
        .bind(participantId)
        .run();

      // 直前の取得判定と連番採番を、挿入と同じSQL文内で実行する。
      const result = await env.DB
        .prepare(`
          INSERT INTO stamps (participant_id, spot_id, scan_order)
          SELECT ?, ?, COALESCE((
            SELECT MAX(scan_order) FROM stamps WHERE participant_id = ?
          ), 0) + 1
          WHERE COALESCE((
            SELECT spot_id FROM stamps
            WHERE participant_id = ?
            ORDER BY scan_order DESC, id DESC LIMIT 1
          ), '') <> ?
        `)
        .bind(participantId, spotId, participantId, participantId, spotId)
        .run();

      if (Number(result.meta?.changes) !== 1) {
        const history = await getHistory(env.DB, participantId);
        return jsonResponse({
          ok: false,
          code: "CONSECUTIVE_DUPLICATE",
          message: "同じ場所を連続して取得することはできません。",
          participantId,
          history,
        }, 409);
      }

      const inserted = await env.DB
        .prepare("SELECT scan_order FROM stamps WHERE id = ? AND participant_id = ?")
        .bind(result.meta?.last_row_id, participantId)
        .first();
      if (!inserted) throw new Error("Inserted stamp not found.");

      const scanOrder = Number(inserted.scan_order);
      const history = await getHistory(env.DB, participantId);

      return jsonResponse({
        ok: true,
        participantId,
        stamp: {
          spotId: spot.id,
          type: spot.type,
          name: spot.name,
          scanOrder,
        },
        history,
      });
    }

    return jsonResponse(
      {
        ok: false,
        error: "Method not allowed.",
      },
      405
    );
  } catch (error) {
    console.error("API request failed", error);
    return jsonResponse({ ok: false, error: "Server error." }, 500);
  }
}
