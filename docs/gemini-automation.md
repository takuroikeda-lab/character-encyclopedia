# Gemini APIによる毎朝の生成・公開

GeminiのWebチャットから外へ送信する方式をやめ、GitHub ActionsがGemini APIを呼び出してファイルを直接受け取る構成。

## 初回設定

1. Google AI StudioでGemini APIキーを発行し、必要なモデルへのアクセス・課金・利用枠を設定する。
2. GitHubリポジトリの Settings → Secrets and variables → Actions → New repository secret で、名前 `GEMINI_API_KEY`、値にAPIキーを登録する。キーをチャットやGitへ貼らない。
3. Actions → **Gemini daily generation** → Run workflow → `preflight` を実行して設定を確認する。これはAPIを呼び出さず、画像生成料金は発生しない。
4. 必要なら `preview` で画像だけを制作し、ArtifactsのZIPを確認する。これはAPIを最大5回呼ぶ有料試験。サイトへは反映しない。
5. `publish-and-enable` を実行する。実画像の生成、検査、GitHub登録、Cloudflareの完全一致確認がすべて成功した後にだけ定期実行を有効化する。

設定ページ: https://github.com/takuroikeda-lab/character-encyclopedia/settings/secrets/actions
実行ページ: https://github.com/takuroikeda-lab/character-encyclopedia/actions/workflows/gemini-generate.yml
APIキー: https://aistudio.google.com/api-keys

初期状態は `config/gemini-automation.json` の `dailyEnabled: false`。APIキーがなくても自動生成は始まらない。GitHubのSecretは、この作業で使っているGitHub連携ツールからは登録できない。

## 運転

- 毎朝7:00（日本時間、UTCでは前日22:00）に起動。GitHubの混雑で遅れることがあり、秒単位の定時保証はしない。
- `publish`: 生成して公開するが、定期実行は有効化しない。
- `publish-and-enable`: 公開確認成功後に定期実行を有効化。
- `disable-daily`: APIキー不要で定期実行を停止。
- 毎日1体。台帳の `generationDateTokyo` が当日なら、再実行しても新規生成を呼ばず、公開内容を再確認する。前日の失敗分を自動で大量生成しない。
- 初期モデルは設定ファイルに固定。テキスト・検査は `gemini-3.8-flash`、画像は `gemini-nano-banana-2.1`。利用可能性・料金はGoogleのAPIプロジェクト側で確認する。
- API呼び出しは1回の試行につき最大5回（設定1回、画像3回、視覚検査1回）。タイムアウト・拒否・利用枠エラー時は有料呼び出しを自動で再試行しない。手動で再試行すると追加料金が発生し得る。
- `preview` の成果物は公開前のため、続く別の生成実行では再生成される。再利用する場合はArtifactsの4ファイルZIPを既存の `imports/gemini/` 取り込み口へ渡す。

## 引き継ぐ制作方針

`prompts/gemini-creative-brief.md` を全API呼び出しへ適用し、ユーザーが好む#050タツミを画風の参照画像として使う（未登録の場合は最新シートにフォールバックする）。既存の動物・名前・設定一覧も渡す。AをBの同一キャラクター参照、A/Bを図鑑シートの参照に使う。

この初期方針は公開済み#049とリポジトリ内の既存指示から復元したもの。Gemini Webチャットの全履歴や、未公開キャラクターの情報は自動取得しない。追加ルールを引き継ぐ場合はこのファイルを編集する。Gemini Web側の定期生成とAPI側を同時に動かすと別々のキャラクターが生成されるため、API側の成功確認後にWeb側の既存定期生成を整理する。

## 公開と失敗時の挙動

生成物はまず `output/gemini-run/` に保存。モデルが返すID・画像パス・sourceなどは採用せず、コードが最新台帳から設定する。3画像をデコードし、別のAPI呼び出しで同一性・番号・文字・欠けを視覚検査する。これは自動検査であり、人間による目視承認ではない。見た目の完全な正しさを保証するものではない。

視覚検査を通った4ファイルZIPだけを既存のGeminiインポーターで検証。画像3点とGemini台帳・監査を単一コミットでmainへ送る。ChatGPT系列には書き込まない。ZIP取り込みと同じ排他グループを使い、mainへの競合したpushは強制上書きしない。

Cloudflare公開後、両系列の台帳と参照画像の完全なバイト一致を確認する。初回公開に成功した場合だけ、公開確認したコミットを記録し、定期実行を有効化する別コミットを作る。

失敗時は公開前の生成物もActions Artifactsに30日保存する（ジョブの強制停止等で保存できない場合を除く）。APIキーや認証ヘッダーは保存しない。登録コミット後にCloudflare確認が失敗した場合は、登録を勝手に巻き戻さず、定期運転の初回有効化を止める。サイト確認の再実行では、当日キャラクターを重複生成しない。

生成時・公開時のエラーはActionsの失敗として残る。GitHub側でActions通知を有効にすれば失敗通知を受け取れる。自動で通知設定を変更する処理は含まない。

## 実装検証と残る条件

オフライン試験はAPI応答を模擬し、生成→パッケージ検証→取り込み、同日重複防止、視覚検査失敗時の非公開、秘密情報を出力しないHTTPエラー処理、画像応答の取り扱い、定期実行の成功ゲートを確認する。模擬画像はサイトへ公開しない。

APIキー登録と実APIでの初回実行が済むまでは、実APIによる画像品質・モデルアクセス・料金・API応答互換性・生成から公開までの通し試験は未確認。初期状態で「完全自動化の稼働確認済み」とは扱わない。

公式仕様:
- https://ai.google.dev/gemini-api/docs/image-generation
- https://ai.google.dev/gemini-api/docs/structured-output
- https://ai.google.dev/api/interactions-api
- https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule

## 2026-10-24 作風・納品方針の更新

企画APIの1回の応答内でA/B/Cのポーズ案を比較し、自動で採用案を選ぶ。比較と採用理由が欠けた場合は画像生成前に停止する。感情・体型・姿勢・小物の情報を既存作品一覧に含め、次回の偏り防止に使う。バッグや手持ち小物、悲しげな長脚の立ち姿を標準にしない。参照タツミの威嚇ポーズ自体も固定しない。

実際に納品するWebP3点を自動視覚検査へ渡し、採用ポーズ・小物・動物・番号・名前・画像同一性を検査する。生成途中のJSONはverified=false、検査成功後のみtrueとする。ZIP作成後に開き直し、検証対象画像との完全一致を確認し、全ファイルのSHA-256をmanifest.jsonに保存する。Artifactsにはポーズ比較・生成画像・ZIP・検査結果を保存。最大5回のAPI呼び出し制限、同日重複防止、番号予約、毎朝7時の運転は維持する。

自動視覚検査は人間の目視ではなく、誤判定の可能性は残る。新方針の画像の出来栄えは次の実生成で確認する。オフライン試験で実API画像を生成したとは扱わない。
