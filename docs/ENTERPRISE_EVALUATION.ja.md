# 企業向け評価ガイド

PHP Safe Migrateの現行版は、**読み取り専用の静的診断**を提供します。自動移行や本番反映の承認には使えません。

1. 本番秘密情報を含まないPHPリポジトリを1件選び、隔離した評価環境で実行します。ルートのDockerfileまたはCompose、可能なら`composer.json`と`composer.lock`を用意してください。
2. Python 3.11以降でインストールし、`php-safe-migrate /path/to/project --refresh --format json > assessment.json`を実行します。`--refresh`はPHP公式サイトに接続します。対象のPHPコードやComposerスクリプトは実行しません。
3. `findings`、`blockers`、`candidate_targets`を確認し、実際に配備されたPHP版・イメージdigest・ベンダーの修正情報を別途照合します。候補は静的な提案であり、互換性の保証ではありません。
4. 既存テスト、拡張モジュール、HTTP応答、DBの整合性を自社の隔離環境で検証し、バックアップと復旧手順を準備してください。本番変更には別途明示的な承認が必要です。
5. 有効だった点、誤検出、未検出を機密情報を除いて[評価フィードバック](https://github.com/FORIFOR/php-safe-migrate/issues/new?template=pilot_feedback.yml)へ共有してください。

ツールにテレメトリーはありません。レポートには社内のイメージ名やパッケージ名が含まれ得るため、外部共有前に確認してください。質問は[Discussions](https://github.com/FORIFOR/php-safe-migrate/discussions)、脆弱性報告は[セキュリティポリシー](../SECURITY.md)を参照してください。現時点でCVEカタログは網羅的ではなく、実行時互換性とデータ保全は検証していません。
