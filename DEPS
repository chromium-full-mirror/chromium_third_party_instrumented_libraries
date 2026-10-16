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
              'object_name': 'd4de19a9bc3d2979f09f74ce23bb4182fd803f8fd02e73a7c7eb4b1c5519c4e0',
              'sha256sum': 'd4de19a9bc3d2979f09f74ce23bb4182fd803f8fd02e73a7c7eb4b1c5519c4e0',
              'size_bytes': 585844795,
              'generation': 1792111736710902,
          },
          # msan-no-origins-resolute-lib
          {
              'object_name': 'ce02284af7031e544a601bf98f2ad1c1af94374c9fd370513029bd9b11715ddb',
              'sha256sum': 'ce02284af7031e544a601bf98f2ad1c1af94374c9fd370513029bd9b11715ddb',
              'size_bytes': 562400266,
              'generation': 1792111746631983,
          },
      ],
  },
}
