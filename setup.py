# -*- coding: ISO-8859-1 -*-
# setup.py: the distutils script
#
import os
import setuptools
import shutil
import sys
import subprocess
import re

from distutils import log
from distutils.command.build_ext import build_ext
from setuptools import Extension

# If you need to change anything, it should be enough to change setup.cfg.

# Remove dist directory if it exists
dist_dir = 'dist'
if os.path.exists(dist_dir):
    log.info(f"Removing existing {dist_dir} directory")
    shutil.rmtree(dist_dir)

VERSION = '0.0.16'

# define sqlite sources
sources = [os.path.join('src', source)
           for source in ["module.c", "connection.c", "cursor.c", "cache.c",
                          "microprotocols.c", "prepare_protocol.c",
                          "statement.c", "util.c", "row.c", "blob.c"]]

# define packages
EXTENSION_MODULE_NAME = "._sqlite3"

# Work around clang raising hard error for unused arguments
if sys.platform == "darwin":
    os.environ['CFLAGS'] = "-Qunused-arguments"
    log.info("CFLAGS: " + os.environ['CFLAGS'])


def parse_openssl_version(opensslv_h_path):
    """
    Parse OpenSSL version number from opensslv.h.
    Returns version string like "3.0.0" or None if parsing fails.
    """
    try:
        with open(opensslv_h_path, 'r', encoding='utf-8') as f:
            content = f.read()
        match = re.search(r'#\s*define\s+OPENSSL_VERSION_TEXT\s+"OpenSSL\s+(\d+\.\d+\.\d+)', content)
        if match:
            return match.group(1)
    except Exception as e:
        pass
    return None

def is_openssl_version_acceptable(version_str):
    """
    Check if version is 3.0.0 or higher.
    """
    if not version_str:
        return False
    parts = list(map(int, version_str.split('.')))
    return parts >= [3, 0, 0]

def find_openssl_on_windows():
    """
    Tries to detect OpenSSL 3.x installation path on Windows with fallback mechanisms.
    Returns a tuple of (include_dir, lib_dir, lib_name).
    """
    # 1. Try environment variable first
    if os.environ.get('OPENSSL_ROOT'):
        openssl_root = os.environ['OPENSSL_ROOT']
        include_dir = os.path.join(openssl_root, 'include')
        lib_dir = os.path.join(openssl_root, 'lib')
        lib_name = 'libcrypto.lib'
        if os.path.exists(os.path.join(lib_dir, lib_name)):
            return include_dir, lib_dir, lib_name
    
    openssl_conf = os.environ.get('OPENSSL_CONF')
    if openssl_conf and os.path.exists(openssl_conf):
        openssl_root = os.path.dirname(os.path.dirname(openssl_conf))
        include_dir = os.path.join(openssl_root, "include")
        lib_dir = os.path.join(openssl_root, "lib")
        opensslv_h = os.path.join(include_dir, "openssl", "opensslv.h")
        version = parse_openssl_version(opensslv_h)
        if os.path.exists(include_dir) and os.path.exists(lib_dir) and is_openssl_version_acceptable(version):
            return include_dir, lib_dir, os.environ.get('OPENSSL_LIBNAME') or 'libcrypto.lib'

    # 2. Search common locations
    potential_locations = [
        os.path.join(os.environ.get('ProgramFiles', r'C:\Program Files'), 'OpenSSL'),
        os.path.join(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)'), 'OpenSSL'),
        os.path.join(os.environ.get('ProgramFiles', r'C:\Program Files'), 'OpenSSL-Win64'),  # important!
        os.path.join(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)'), 'OpenSSL-Win32'),
        os.path.join(os.environ.get('VCPKG_ROOT', ''), 'installed', 'x64-windows'),
        os.path.join(os.environ.get('VCPKG_ROOT', ''), 'installed', 'x86-windows'),
        os.path.join(os.environ.get('ProgramFiles', r'C:\Program Files'), 'Strawberry', 'c', 'openssl'),
        os.path.join(os.environ.get('ProgramFiles', r'C:\Program Files'), 'Git', 'mingw64', 'openssl'),
        os.path.expanduser(r'~\scoop\apps\openssl'),
    ]

    version_subdirs = ["", "openssl", "openssl-3", "openssl-1.1"]

    for base_location in potential_locations:
        if not os.path.exists(base_location):
            continue
        for subdir in version_subdirs:
            openssl_root = os.path.join(base_location, subdir) if subdir else base_location
            include_dir = os.path.join(openssl_root, "include")
            lib_dir = os.path.join(openssl_root, "lib")
            opensslv_h = os.path.join(include_dir, "openssl", "opensslv.h")
            if os.path.exists(opensslv_h) and os.path.exists(lib_dir):
                version = parse_openssl_version(opensslv_h)
                if is_openssl_version_acceptable(version):
                    for lib_name in ['libcrypto.lib', 'libeay32.lib', 'crypto.lib']:
                        if os.path.exists(os.path.join(lib_dir, lib_name)):
                            return include_dir, lib_dir, lib_name

    # 3. Try from PATH
    try:
        which_openssl = subprocess.check_output(["where", "openssl.exe"],
                                               stderr=subprocess.DEVNULL,
                                               universal_newlines=True).strip().split('\n')[0]
        if which_openssl:
            openssl_bin_dir = os.path.dirname(which_openssl)
            openssl_root = os.path.dirname(openssl_bin_dir)
            include_dir = os.path.join(openssl_root, "include")
            lib_dir = os.path.join(openssl_root, "lib")
            opensslv_h = os.path.join(include_dir, "openssl", "opensslv.h")
            if os.path.exists(opensslv_h):
                version = parse_openssl_version(opensslv_h)
                if is_openssl_version_acceptable(version):
                    for lib_name in ['libcrypto.lib', 'libeay32.lib', 'crypto.lib']:
                        if os.path.exists(os.path.join(lib_dir, lib_name)):
                            return include_dir, lib_dir, lib_name
    except Exception:
        pass

    raise RuntimeError(
        "OpenSSL 3.x not found. Please install OpenSSL 3.x and set correct path or set OPENSSL_CONF."
    )

# Find OpenSSL prefix on non-Windows platforms
def find_openssl_prefix() -> str:
    """
    Tries to detect OpenSSL installation path (Linux, macOS Homebrew, or system default).
    """
    # For macOS, try Homebrew first
    if sys.platform == "darwin":
        brew_candidates = ["openssl@3", "openssl@1.1"]
        for formula in brew_candidates:
            try:
                prefix = subprocess.check_output(
                    ["brew", "--prefix", formula],
                    stderr=subprocess.DEVNULL,
                    universal_newlines=True
                ).strip()
                if os.path.exists(os.path.join(prefix, "include", "openssl", "crypto.h")):
                    return prefix
            except Exception:
                continue

    # Linux-specific paths to check
    if sys.platform.startswith('linux'):
        linux_paths = [
            "/usr",  # Standard location
            "/usr/local",  # Common alternative
            "/usr/local/opt/openssl",  # Custom installs
            "/opt/openssl",  # Custom installs
            "/usr/include/openssl",  # Some distros
        ]
        
        # Check for common package managers to provide better error messages
        package_managers = {
            "apt": "apt install libssl-dev",
            "dnf": "dnf install openssl-devel",
            "yum": "yum install openssl-devel",
            "pacman": "pacman -S openssl"
        }
        
        for path in linux_paths:
            if os.path.exists(os.path.join(path, "include", "openssl", "crypto.h")):
                return path
            
        # If we're here, OpenSSL wasn't found on Linux - prepare helpful message
        install_cmd = None
        for pm, cmd in package_managers.items():
            try:
                subprocess.check_output(["which", pm], stderr=subprocess.DEVNULL)
                install_cmd = cmd
                break
            except Exception:
                continue
                
        if install_cmd:
            error_msg = f"OpenSSL headers not found. Please install OpenSSL development package with: `{install_cmd}`"
        else:
            error_msg = "OpenSSL headers not found. Please install OpenSSL development package for your distribution."
        raise RuntimeError(error_msg)

    # Common system paths (fallback for all platforms)
    common_paths = ["/usr/local", "/opt/homebrew", "/usr"]
    for path in common_paths:
        if os.path.exists(os.path.join(path, "include", "openssl", "crypto.h")):
            return path

    raise RuntimeError(
        "OpenSSL headers not found. Please install OpenSSL (e.g., `brew install openssl@3`)."
    )


def quote_argument(arg):
    q = '\\"' if sys.platform == 'win32' and sys.version_info < (3, 8) else '"'
    return q + arg + q

define_macros = [
    ('MODULE_NAME', quote_argument("sqlcipher3.dbapi2")),
    ('HAVE_STDINT_H', '1'),
    ('HAVE_INTTYPES_H', '1'),
]

class SystemLibSqliteBuilder(build_ext):
    description = "Builds a C extension linking against system SQLCipher/SQLite3 library"

    def find_system_sqlcipher(self):
        """
        Find system-installed SQLCipher or SQLite3.
        Returns (include_dir, library_dir, library_name).
        """
        candidates = []

        if sys.platform == "win32":
            # Check VCPKG (assume vcpkg has SQLCipher installed)
            vcpkg_root = os.environ.get('VCPKG_ROOT', r'C:\vcpkg')
            if vcpkg_root and os.path.exists(vcpkg_root):
                for triplet in ['x64-windows', 'x86-windows']:
                    prefix = os.path.join(vcpkg_root, 'installed', triplet)
                    if os.path.exists(os.path.join(prefix, 'include', 'sqlcipher', 'sqlite3.h')):
                        candidates.append((os.path.join(prefix, 'include'),
                                           os.path.join(prefix, 'lib'),
                                           'sqlcipher'))
        else:
            # macOS (Homebrew/MacPorts) or Linux
            brew_prefixes = [
                "/usr/local/opt/sqlcipher",
                "/usr/local/opt/sqlite",
                "/opt/homebrew/opt/sqlcipher",
                "/opt/homebrew/opt/sqlite",
            ]
            linux_prefixes = [
                "/usr",
                "/usr/local",
                "/opt/sqlcipher",
                "/opt/sqlite",
            ]
            paths = brew_prefixes if sys.platform == "darwin" else linux_prefixes
            for prefix in paths:
                if os.path.exists(os.path.join(prefix, 'include', 'sqlcipher', 'sqlite3.h')):
                    candidates.append((os.path.join(prefix, 'include'),
                                       os.path.join(prefix, 'lib'),
                                       'sqlcipher'))

        if not candidates:
            raise RuntimeError("Could not find a system SQLCipher/SQLite3 installation.")

        # Pick the first candidate
        return candidates[0]

    def build_extension(self, ext):
        log.info(self.description)

        try:
            include_dir, lib_dir, lib_name = self.find_system_sqlcipher()

            ext.include_dirs.append(include_dir)
            ext.library_dirs.append(lib_dir)
            ext.libraries.append(lib_name)
            log.info(f"Found SQLCipher/SQLite3: include={include_dir}, lib={lib_dir}, library={lib_name}")

            # Add macros
            ext.define_macros.append(('SQLITE_HAS_CODEC', '1'))
            ext.define_macros.append(('HAVE_STDINT_H', '1'))
            ext.define_macros.append(('HAVE_INTTYPES_H', '1'))
        except RuntimeError as e:
            log.error(str(e))
            raise

        build_ext.build_extension(self, ext)

class AmalgationLibSqliteBuilder(build_ext):
    description = "Builds a C extension using a sqlcipher amalgamation"

    amalgamation_root = "."
    amalgamation_header = os.path.join(amalgamation_root, 'sqlite3.h')
    amalgamation_source = os.path.join(amalgamation_root, 'sqlite3.c')

    header_dir = os.path.join(amalgamation_root, 'sqlcipher')
    header_file = os.path.join(header_dir, 'sqlite3.h')
    
    sqlcipher_submodule_path = os.path.join("dependencies", "sqlcipher")

    amalgamation_message = ('Sqlcipher amalgamation not found. Please download'
                            ' or build the amalgamation and make sure the '
                            'following files are present in the sqlcipher3 '
                            'folder: sqlite3.h, sqlite3.c')

    def build_sqlcipher_amalgamation(self, force_rebuild=True):
        """Build SQLCipher amalgamation from the git submodule."""
        log.info("Building SQLCipher amalgamation from submodule")
    
        if not os.path.exists(self.sqlcipher_submodule_path):
            log.error(f"SQLCipher submodule not found at {self.sqlcipher_submodule_path}")
            raise RuntimeError("SQLCipher submodule not found. Please run 'git submodule update --init'")
        
        current_dir = os.getcwd()
        try:
            # Change to the sqlcipher submodule directory
            os.chdir(self.sqlcipher_submodule_path)
            
            # Clean existing build if forcing rebuild
            if force_rebuild:
                log.info("Cleaning existing SQLCipher build")
                subprocess.run(["make", "clean"], check=False)
            
            # Run configure
            log.info("Running ./configure in SQLCipher submodule")
            configure_result = subprocess.run(["sh","./configure"], check=True)
            
            # Run make sqlite.c
            log.info("Running make sqlite.c in SQLCipher submodule")
            make_result = subprocess.run(["make", "sqlite3.c"], check=True)
            
            # Return to the original directory
            os.chdir(current_dir)
            
            # Copy the generated files to the root directory
            log.info("Copying SQLCipher amalgamation files to root directory")
            submodule_header = os.path.join(self.sqlcipher_submodule_path, "sqlite3.h")
            submodule_source = os.path.join(self.sqlcipher_submodule_path, "sqlite3.c")
            
            shutil.copy(submodule_header, self.amalgamation_header)
            shutil.copy(submodule_source, self.amalgamation_source)
            
            log.info("SQLCipher amalgamation build completed successfully")
            return True
        except subprocess.CalledProcessError as e:
            log.error(f"Error building SQLCipher amalgamation: {str(e)}")
            raise RuntimeError(f"Failed to build SQLCipher amalgamation: {str(e)}")
        except Exception as e:
            log.error(f"Unexpected error building SQLCipher amalgamation: {str(e)}")
            raise
        finally:
            # Ensure we return to the original directory
            os.chdir(current_dir)

    def check_amalgamation(self):
        # Check if we should force rebuild based on environment variable
        force_rebuild = os.environ.get('SQLCIPHER_FORCE_REBUILD', '').lower() in ('1', 'true', 'yes')
        
        if not self.build_sqlcipher_amalgamation(force_rebuild=force_rebuild):
            raise RuntimeError(self.amalgamation_message)

        if not os.path.exists(self.header_dir):
            os.mkdir(self.header_dir)
        if not os.path.exists(self.header_file):
            shutil.copy(self.amalgamation_header, self.header_file)

    def build_extension(self, ext):
        log.info(self.description)

        # it is responsibility of user to provide amalgamation
        self.check_amalgamation()

        # Feature-ful library.
        features = (
            'ENABLE_FTS3',
            'ENABLE_FTS3_PARENTHESIS',
            'ENABLE_FTS4',
            'ENABLE_FTS5',
            'ENABLE_JSON1',
            'ENABLE_LOAD_EXTENSION',
            'ENABLE_RTREE',
            'ENABLE_STAT4',
            'ENABLE_UPDATE_DELETE_LIMIT',
            'HAS_CODEC',  # Required for SQLCipher.
            'SOUNDEX',
            'USE_URI',
        )
        for feature in features:
            ext.define_macros.append(('SQLITE_%s' % feature, '1'))

        # Required for SQLCipher.
        ext.define_macros.append(("SQLITE_TEMP_STORE", "2"))

        # Increase the maximum number of "host parameters".
        ext.define_macros.append(("SQLITE_MAX_VARIABLE_NUMBER", "250000"))

        # Additional nice-to-have.
        ext.define_macros.extend([
            ('SQLITE_DEFAULT_PAGE_SIZE', '4096'),
            ('SQLITE_DEFAULT_CACHE_SIZE', '-8000'),
            ("SQLITE_EXTRA_INIT", "sqlcipher_extra_init"),
            ("SQLITE_EXTRA_SHUTDOWN", "sqlcipher_extra_shutdown"),
        ])  # 8MB.

        ext.include_dirs.append(self.amalgamation_root)
        ext.sources.append(os.path.join(self.amalgamation_root, "sqlite3.c"))

        if sys.platform != "win32":
            # Include math library, required for fts5, and crypto.
            openssl_prefix = find_openssl_prefix()
            ext.include_dirs.append(os.path.join(openssl_prefix, "include"))
            ext.extra_link_args.extend([
                "-L" + os.path.join(openssl_prefix, "lib"),
                "-lcrypto",
                "-lm"
            ])
        else:
            # Use improved OpenSSL detection for Windows
            try:
                include_dir, lib_dir, lib_name = find_openssl_on_windows()
                ext.include_dirs.append(include_dir)
                ext.define_macros.append(("inline", "__inline"))
                ext.libraries.extend(['libcrypto', 'libssl'])
                ext.library_dirs.append(lib_dir)
                log.info(f"Found OpenSSL on Windows: include={include_dir}, lib={lib_dir}, using {lib_name}")
            except RuntimeError as e:
                log.error(str(e))
                raise

        build_ext.build_extension(self, ext)

    def __setattr__(self, k, v):
        # Make sure we don't link against the SQLite
        # library, no matter what setup.cfg says
        if k == "libraries":
            v = None
        self.__dict__[k] = v


def get_setup_args():
    return dict(
        name="sqlcipher3-nexa",
        version=VERSION,
        description="DB-API 2.0 interface for SQLCipher 3.x",
        long_description='',
        author="NexaAI",
        author_email="dev@nexa4ai.com",
        license="zlib/libpng",
        platforms="ALL",
        url="https://github.com/vinovo/sqlcipher3",
        package_dir={"sqlcipher3": "sqlcipher3"},
        packages=["sqlcipher3"],
        ext_modules=[Extension(
            name="sqlcipher3._sqlite3",
            sources=sources,
            define_macros=define_macros)
        ],
        include_package_data=True,
        package_data={
            '': ['dependencies/**/*'],
        },
        classifiers=[
            "Development Status :: 4 - Beta",
            "Intended Audience :: Developers",
            "License :: OSI Approved :: zlib/libpng License",
            "Operating System :: MacOS :: MacOS X",
            "Operating System :: Microsoft :: Windows",
            "Operating System :: POSIX",
            "Programming Language :: C",
            "Programming Language :: Python",
            "Topic :: Database :: Database Engines/Servers",
            "Topic :: Software Development :: Libraries :: Python Modules"],
        cmdclass = {
            "build_static": AmalgationLibSqliteBuilder,
            "build_ext": SystemLibSqliteBuilder,  # use dynamic linking by default
        }
    )


if __name__ == "__main__":
    setuptools.setup(**get_setup_args())
