# GEMINI DAILY CHARACTER WORKFLOW

1日1体のオリジナルIP候補を生成する。

## 固定ルール
- ChatGPT版とは別シリーズとして管理する。
- Gemini内では #001 から独立採番する。
- 既存IP・特定作家の直接模倣はしない。
- 大人にも刺さる、クセ・哀愁・軽い不条理・小さな優しさを持つ。
- 全身、強いシルエット、少ない色、点目、非対称、1キャラ1記号。
- 同じシルエットを連続させない。

## 毎日作るもの
A 通常版：シンプルな全身2D、黒線、少ない色、ビビッド単色背景。
B グラフィック版：同じキャラをKustom Kulture / 60s underground / lowbrow / psychobilly / American Pop / vintage screen-printの空気感で再構成。ただし既存作品の直接模倣は禁止。

## character.json
id, slug, nameJa, nameEn, animal(該当時), concept, emotionTheme, status=MAYBE, verified=true, source=gemini, images を出力する。

## GitHubへ渡すZIP構成
gemini_daily_import.zip
├─ imports/
│  └─ gemini-character.json
└─ public/
   └─ gemini/
      └─ characters/
         └─ NNN/
            ├─ main.webp
            ├─ a.webp
            └─ b.webp

画像はWebPで書き出す。
ZIPをGitHubリポジトリの imports/gemini_daily_import.zip としてアップロードすると、自動でGemini図鑑へ登録される。
