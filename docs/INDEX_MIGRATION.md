# D1取得順序の一意性制約：検証・適用手順（ドラフト）

## 現状
- 本番D1の `stamps` は `id INTEGER PRIMARY KEY` と、`participant_id`, `spot_id`, `acquired_at`, `scan_order` を持つ。
- `PRAGMA index_list("stamps")` で確認した既存インデックス2件はどちらも UNIQUE=0。
- 2026-11-20 のユーザーによる重複確認SQLでは、同一 `(participant_id, scan_order)` の重複は0件だった。
- この情報は「現時点の本番データが安全」である保証ではない。適用直前に再検査する。

## 提案する変更
`migrations/0001_unique_scan_order.sql` は次の制約を追加する。

```sql
CREATE UNIQUE INDEX IF NOT EXISTS idx_stamps_participant_scan_order
  ON stamps (participant_id, scan_order);
```

- 同一参加者の同一取得順序の重複を防止する。
- A→B→A の再訪問は別の `scan_order` として記録できる。
- **獲得数は引き続き DISTINCT spot_id で数える。**
- SQLをリポジトリに追加しただけでは Cloudflare D1 のスキーマは変化しない。

## 検証（本番を変更しない）
1. リポジトリのチェックアウトで `python -m unittest discover -s tests -v` を実行する（標準ライブラリのみ）。実際の `functions/api.js` に埋め込まれた INSERT 文とmigrationを使用する。
2. 別の検証用D1を用意し、**公開PagesのProductionと同じD1を指していないこと**を確認する。現在リポジトリには Wrangler のDBバインディング設定がないため、これを事前に追加・確認する必要がある。
3. 検証用D1にテーブル・スポットのテストデータを用意する。
4. 検証用D1で以下の読み取り専用SQLを実行する。

```sql
SELECT participant_id, scan_order, COUNT(*) AS n
FROM stamps
GROUP BY participant_id, scan_order
HAVING COUNT(*) > 1
ORDER BY n DESC
LIMIT 20;
```

5. 重複がないことを確認して、**検証用D1に限り** `migrations/0001_unique_scan_order.sql` を実行する。
6. `PRAGMA index_list("stamps");` の新規インデックスが `unique=1` であることと、`PRAGMA index_info("idx_stamps_participant_scan_order");` の列順を確認する。
7. Preview環境から v1→v1（409）・v1→v2→v1（3履歴・獲得2か所）・異なる参加者・同時送信・リセット拒否を検証する。DB制約に衝突した場合は `STAMP_WRITE_CONFLICT` を409で返す。
8. 制約違反がある場合、原因を解析してデータの復元や訂正方針を決定する。既存履歴の自動削除・上書きは行わない。

## 本番への適用（別途承認が必要）
- 実行直前に本番DBのバックアップ・復元手順を確認し、重複検査を**再実行**する。
- 検証用D1と本番D1のIDおよび `DB` バインディング先を明確に分ける。
- 既存の公開APIに影響する変更は、DB側制約とコードの公開順序を計画した上で実施する。
- 現在のドラフトPRを**無条件でマージしない**。データベースのマイグレーションは自動で適用されない。
- ロールバック時にはindexを取り消せるが、実施には影響確認と運用者の承認が必要。

## 残る本番リスク
- `participantId` をクライアントから受け取るだけで本人確認がないため、他者の履歴取得・スタンプ付与が可能。次の優先対策。
- `/api` にサーバー側のレート制限や認証がなく、QRコードURL自体が場所への到着証明にはならない。
- 今回の一意性制約は順序の重複防止であり、すべての不正・同時アクセスの問題を解消するわけではない。
