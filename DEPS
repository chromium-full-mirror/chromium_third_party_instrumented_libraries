use_relative_paths = True

vars = {
  # This exists so that upstream projects can control it.
  'checkout_instrumented_libraries': True,

  # condition to allowlist deps for non-git-source processing.
  'non_git_source': 'True',
}

deps = {

  'binaries': {
      'dep_type': 'gcs',
      'condition': 'checkout_instrumented_libraries and non_git_source',
      'bucket': 'chromium-instrumented-libraries',
      'objects': [
          # msan-chained-origins-resolute-lib
          {
              'object_name': '182c261d2c03b8b973929b8acbadaeb838883245f69fbaa07eee011a902a2fa5',
              'sha256sum': '182c261d2c03b8b973929b8acbadaeb838883245f69fbaa07eee011a902a2fa5',
              'size_bytes': 586254578,
              'generation': 1794707656092681,
          },
          # msan-no-origins-resolute-lib
          {
              'object_name': '03a9297e9e14b3dfd0f8da44ef760c0e6319727656b4062e212be7debaaea297',
              'sha256sum': '03a9297e9e14b3dfd0f8da44ef760c0e6319727656b4062e212be7debaaea297',
              'size_bytes': 562614137,
              'generation': 1794707666528524,
          },
      ],
  },
}
