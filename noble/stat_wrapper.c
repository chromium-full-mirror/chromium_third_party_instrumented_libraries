#include <stddef.h>
#include <sys/stat.h>
#include <sys/statfs.h>
#include <sys/statvfs.h>
#include <sys/vfs.h>

void __msan_unpoison(const volatile void*, size_t);

int __real_stat(const char* restrict pathname, struct stat* restrict buf);
int __real_fstat(int fd, struct stat* buf);
int __real_lstat(const char* restrict pathname, struct stat* restrict buf);
int __real_fstatat(int dirfd,
                   const char* restrict pathname,
                   struct stat* restrict buf,
                   int flags);
int __real_statfs(const char* path, struct statfs* buf);
int __real_fstatfs(int fd, struct statfs* buf);
int __real_statvfs(const char* path, struct statvfs* buf);
int __real_fstatvfs(int fd, struct statvfs* buf);
int __real_statx(int dirfd,
                 const char* restrict pathname,
                 int flags,
                 unsigned int mask,
                 struct statx* restrict buf);

int __real_stat64(const char* restrict pathname, struct stat64* restrict buf);
int __real_fstat64(int fd, struct stat64* buf);
int __real_lstat64(const char* restrict pathname, struct stat64* restrict buf);
int __real_fstatat64(int dirfd,
                     const char* restrict pathname,
                     struct stat64* restrict buf,
                     int flags);
int __real___fstat64(int fd, struct stat64* buf);
int __real___fxstat64(int ver, int fd, struct stat64* buf);
int __real___fxstatat64(int ver,
                        int dirfd,
                        const char* pathname,
                        struct stat64* buf,
                        int flags);
int __real___lxstat64(int ver, const char* pathname, struct stat64* buf);
int __real___xstat64(int ver, const char* pathname, struct stat64* buf);
int __real_fstatfs64(int fd, struct statfs64* buf);
int __real_fstatvfs64(int fd, struct statvfs64* buf);
int __real_statfs64(const char* path, struct statfs64* buf);
int __real_statvfs64(const char* path, struct statvfs64* buf);

__attribute__((visibility("default"))) __attribute__((weak)) int __wrap_stat(
    const char* restrict pathname,
    struct stat* restrict buf) {
  int res = __real_stat(pathname, buf);
  __msan_unpoison(buf, sizeof(*buf));
  return res;
}

__attribute__((visibility("default"))) __attribute__((weak)) int __wrap_fstat(
    int fd,
    struct stat* buf) {
  int res = __real_fstat(fd, buf);
  __msan_unpoison(buf, sizeof(*buf));
  return res;
}

__attribute__((visibility("default"))) __attribute__((weak)) int __wrap_lstat(
    const char* restrict pathname,
    struct stat* restrict buf) {
  int res = __real_lstat(pathname, buf);
  __msan_unpoison(buf, sizeof(*buf));
  return res;
}

__attribute__((visibility("default"))) __attribute__((weak)) int __wrap_fstatat(
    int dirfd,
    const char* restrict pathname,
    struct stat* restrict buf,
    int flags) {
  int res = __real_fstatat(dirfd, pathname, buf, flags);
  __msan_unpoison(buf, sizeof(*buf));
  return res;
}

__attribute__((visibility("default"))) __attribute__((weak)) int __wrap_statfs(
    const char* path,
    struct statfs* buf) {
  int res = __real_statfs(path, buf);
  __msan_unpoison(buf, sizeof(*buf));
  return res;
}

__attribute__((visibility("default"))) __attribute__((weak)) int __wrap_fstatfs(
    int fd,
    struct statfs* buf) {
  int res = __real_fstatfs(fd, buf);
  __msan_unpoison(buf, sizeof(*buf));
  return res;
}

__attribute__((visibility("default"))) __attribute__((weak)) int __wrap_statvfs(
    const char* path,
    struct statvfs* buf) {
  int res = __real_statvfs(path, buf);
  __msan_unpoison(buf, sizeof(*buf));
  return res;
}

__attribute__((visibility("default"))) __attribute__((weak)) int
__wrap_fstatvfs(int fd, struct statvfs* buf) {
  int res = __real_fstatvfs(fd, buf);
  __msan_unpoison(buf, sizeof(*buf));
  return res;
}

__attribute__((visibility("default"))) __attribute__((weak)) int __wrap_statx(
    int dirfd,
    const char* restrict pathname,
    int flags,
    unsigned int mask,
    struct statx* restrict buf) {
  int res = __real_statx(dirfd, pathname, flags, mask, buf);
  __msan_unpoison(buf, sizeof(*buf));
  return res;
}

__attribute__((visibility("default"))) __attribute__((weak)) int __wrap_stat64(
    const char* restrict pathname,
    struct stat64* restrict buf) {
  int res = __real_stat64(pathname, buf);
  __msan_unpoison(buf, sizeof(*buf));
  return res;
}

__attribute__((visibility("default"))) __attribute__((weak)) int __wrap_fstat64(
    int fd,
    struct stat64* buf) {
  int res = __real_fstat64(fd, buf);
  __msan_unpoison(buf, sizeof(*buf));
  return res;
}

__attribute__((visibility("default"))) __attribute__((weak)) int __wrap_lstat64(
    const char* restrict pathname,
    struct stat64* restrict buf) {
  int res = __real_lstat64(pathname, buf);
  __msan_unpoison(buf, sizeof(*buf));
  return res;
}

__attribute__((visibility("default"))) __attribute__((weak)) int
__wrap_fstatat64(int dirfd,
                 const char* restrict pathname,
                 struct stat64* restrict buf,
                 int flags) {
  int res = __real_fstatat64(dirfd, pathname, buf, flags);
  __msan_unpoison(buf, sizeof(*buf));
  return res;
}

__attribute__((visibility("default"))) __attribute__((weak)) int
__wrap___fstat64(int fd, struct stat64* buf) {
  int res = __real___fstat64(fd, buf);
  __msan_unpoison(buf, sizeof(*buf));
  return res;
}

__attribute__((visibility("default"))) __attribute__((weak)) int
__wrap___fxstat64(int ver, int fd, struct stat64* buf) {
  int res = __real___fxstat64(ver, fd, buf);
  __msan_unpoison(buf, sizeof(*buf));
  return res;
}

__attribute__((visibility("default"))) __attribute__((weak)) int
__wrap___fxstatat64(int ver,
                    int dirfd,
                    const char* pathname,
                    struct stat64* buf,
                    int flags) {
  int res = __real___fxstatat64(ver, dirfd, pathname, buf, flags);
  __msan_unpoison(buf, sizeof(*buf));
  return res;
}

__attribute__((visibility("default"))) __attribute__((weak)) int
__wrap___lxstat64(int ver, const char* pathname, struct stat64* buf) {
  int res = __real___lxstat64(ver, pathname, buf);
  __msan_unpoison(buf, sizeof(*buf));
  return res;
}

__attribute__((visibility("default"))) __attribute__((weak)) int
__wrap___xstat64(int ver, const char* pathname, struct stat64* buf) {
  int res = __real___xstat64(ver, pathname, buf);
  __msan_unpoison(buf, sizeof(*buf));
  return res;
}

__attribute__((visibility("default"))) __attribute__((weak)) int
__wrap_fstatfs64(int fd, struct statfs64* buf) {
  int res = __real_fstatfs64(fd, buf);
  __msan_unpoison(buf, sizeof(*buf));
  return res;
}

__attribute__((visibility("default"))) __attribute__((weak)) int
__wrap_fstatvfs64(int fd, struct statvfs64* buf) {
  int res = __real_fstatvfs64(fd, buf);
  __msan_unpoison(buf, sizeof(*buf));
  return res;
}

__attribute__((visibility("default"))) __attribute__((weak)) int
__wrap_statfs64(const char* path, struct statfs64* buf) {
  int res = __real_statfs64(path, buf);
  __msan_unpoison(buf, sizeof(*buf));
  return res;
}

__attribute__((visibility("default"))) __attribute__((weak)) int
__wrap_statvfs64(const char* path, struct statvfs64* buf) {
  int res = __real_statvfs64(path, buf);
  __msan_unpoison(buf, sizeof(*buf));
  return res;
}
