# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Support multi-layer marker collection for test case attributes (module/class/function level)
- Improve parser to correctly extract tags with deduplication across layers
- Support for HTTP request header injection during test execution
- Add test case identification to API requests via X-Testsolar-Testcase header

### Changed
- Update file reporting mode in run script
- Refactor reporter implementation to use FileReporter instead of Reporter
- Improve parse_case_attributes to use item.iter_markers() for complete marker collection
- Remove getattr/hasattr usage in favor of direct attribute access with try/except fallback

### Fixed
- Improve test case collection and execution with better file handling