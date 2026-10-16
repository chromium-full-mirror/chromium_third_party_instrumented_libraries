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
          # msan-chained-origins-noble-lib
          {
              'object_name': 'd9e7f16940320353e061e06111705d49ae5043ed092db352b682dd4a184fa08f',
              'sha256sum': 'd9e7f16940320353e061e06111705d49ae5043ed092db352b682dd4a184fa08f',
              'size_bytes': 519633093,
              'generation': 1787961433083449,
          },
          # msan-no-origins-noble-lib
          {
              'object_name': '36a06c938048f0920cf41dce2d58aae7712aa24fdd91787250b2a6c21cf4283b',
              'sha256sum': '36a06c938048f0920cf41dce2d58aae7712aa24fdd91787250b2a6c21cf4283b',
              'size_bytes': 499074429,
              'generation': 1787961441197649,
          },
          # msan-chained-origins-resolute-lib
          {
              'object_name': '3d9c1a1614a2d3d8bdedb7495763f1b6b35db36525d0f8e30afc2e40a18c715b',
              'sha256sum': '3d9c1a1614a2d3d8bdedb7495763f1b6b35db36525d0f8e30afc2e40a18c715b',
              'size_bytes': 585476778,
              'generation': 1792166825262546,
          },
          # msan-no-origins-resolute-lib
          {
              'object_name': '07c3b192849e17de23be013d9d5adb2ee9d2c9f2b876a0703660e4536c66ad85',
              'sha256sum': '07c3b192849e17de23be013d9d5adb2ee9d2c9f2b876a0703660e4536c66ad85',
              'size_bytes': 561968922,
              'generation': 1792166836644676,
          },
      ],
  },
}
