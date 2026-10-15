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
              'object_name': '230ca366b406a31f29ab2e8e798c0d4c36108b40e134bb3f2b4c5b7b632ecdf7',
              'sha256sum': '230ca366b406a31f29ab2e8e798c0d4c36108b40e134bb3f2b4c5b7b632ecdf7',
              'size_bytes': 584327142,
              'generation': 1792098025283214,
          },
          # msan-no-origins-resolute-lib
          {
              'object_name': 'df9ac72b96449bf0b6cb1b5a4477ce873e77c29387052f2db427ec7a663ef983',
              'sha256sum': 'df9ac72b96449bf0b6cb1b5a4477ce873e77c29387052f2db427ec7a663ef983',
              'size_bytes': 560890161,
              'generation': 1792098033635966,
          },
      ],
  },
}
