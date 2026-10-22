# 企業向け評価ガイド

PHP Safe Migrateの現行版は、**読み取り専用の静的診断**と、別コマンドによる**限定的な隔離検証**を提供します。自動移行や本番反映の承認には使えません。企業導入で必要となる保証の対象と必須証拠は[本番移行の安全性をどう保証するか](PRODUCTION_ASSURANCE.ja.md)にまとめています。

1. 本番秘密情報を含まないPHPリポジトリを1件選び、隔離した評価環境で実行します。ルートのDockerfileまたはCompose、可能なら`composer.json`と`composer.lock`を用意してください。
2. Python 3.11以降でインストールし、`php-safe-migrate /path/to/project --refresh --format json > assessment.json`を実行します。`--refresh`はPHP公式サイトに接続します。対象のPHPコードやComposerスクリプトは実行しません。
3. `findings`、`blockers`、`candidate_targets`を確認し、実際に配備されたPHP版・イメージdigest・ベンダーの修正情報を別途照合します。候補は静的な提案であり、互換性の保証ではありません。
4. 機密情報を除いた使い捨てのコピーで、[隔離検証コマンド](ISOLATED_VERIFICATION.ja.md)を使い、指定したPHPテスト、宣言済み拡張、ロック済みComposerプラットフォーム要件を確認できます。これはアプリ全体の互換性を保証しません。
5. HTTP応答、DBの整合性、バックアップからの復元を自社の非本番環境で別途検証してください。いずれかに説明できない差分があれば移行を止めます。本番変更には対象環境と計画を指定した別途の明示的な承認が必要です。
6. 有効だった点、誤検出、未検出を機密情報を除いて[評価フィードバック](https://github.com/FORIFOR/php-safe-migrate/issues/new?template=pilot_feedback.yml)へ共有してください。

ツールにテレメトリーはありません。レポートには社内のイメージ名やパッケージ名が含まれ得るため、外部共有前に確認してください。質問は[Discussions](https://github.com/FORIFOR/php-safe-migrate/discussions)、脆弱性報告は[セキュリティポリシー](../SECURITY.md)を参照してください。現時点でCVEカタログは網羅的ではなく、実案件の実行時互換性とデータ保全は検証していません。
