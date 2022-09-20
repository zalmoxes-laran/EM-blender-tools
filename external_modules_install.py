import subprocess
import sys
import os
import bpy
import site
import pkg_resources

from bpy.props import BoolProperty

#from .google_credentials import check_google_modules

from .blender_pip import Pip
Pip._ensure_user_site_package()

import logging
log = logging.getLogger(__name__)

class OBJECT_OT_install_missing_modules(bpy.types.Operator):
    bl_idname = "install_missing.modules"
    bl_label = "missing modules"
    bl_options = {"REGISTER", "UNDO"}

    is_install : BoolProperty()

    def execute(self, context):
        if self.is_install:
            install_modules()
        else:
            uninstall_modules()
        check_google_modules()
        return {'FINISHED'}

def google_list_modules():
    list_of_modules =[
        #"google-api-python-client==2.28.0",
        "google-auth-httplib2==0.1.0",
        "google-auth-oauthlib==0.4.6",
        "six==1.16.0",
        "httplib2",
        "pyparsing==2.4.7",
        "uritemplate",
        "google==3.0.0",
        #"googleapiclient"
        "google.auth==2.3.2",
        "google-api-core==2.2.2",
        "google-api-python-client==2.31.0",
        "pyasn1==0.4.8",
        "pyasn1_modules==0.2.8",
        "rsa==4.7.2",
        "cachetools==4.2.4",
        "requests_oauthlib==1.3.0",
        "oauthlib==3.1.1",
        "python-telegram-bot==13.7",
        "pytz==2021.3",
        "apscheduler==3.8.1",
        "tzlocal==4.1",
        "pytz-deprecation-shim==0.1.0.post0",
        "tornado==6.1",
        "exchange==0.3"
        ]
    return list_of_modules

def install_modules():
    Pip.upgrade_pip()
    list_of_modules = google_list_modules()
    for module_istall in list_of_modules:
        Pip.install(module_istall)

def uninstall_modules():
    list_of_modules = google_list_modules()
    for module_istall in list_of_modules:
        Pip.uninstall(module_istall)

def old_install_modules():
    
    packages_path = site.getusersitepackages()
    sys.path.insert(0, packages_path )

    is_windows = sys.platform.startswith('win')
    if is_windows:
        print("Il sistema è windows")
        python_exe = os.path.join(sys.prefix, 'bin', 'python.exe')
        python_libs = os.path.join(sys.prefix, 'lib', 'site-packages')
        #python_libs = python_libs.replace('\\\ ', '\\')
    is_mac = sys.platform.startswith('darwin')
    if is_mac:
        python_exe = os.path.join(sys.prefix, 'bin', 'python3.9')
        python_exe = python_exe.replace(' ', '\\ ')
        python_libs = os.path.join(sys.prefix, 'lib', 'site-packages')
        python_libs = python_libs.replace(' ', '\\ ')
    is_linux = sys.platform.startswith('linux') # correggere
    print(python_libs)
    sys.path.insert(0, python_libs )
    #print(str(python_exe))

    list_of_modules =["google-api-python-client", "google-auth-httplib2", "google-auth-oauthlib", "googleapiclient"]

    # upgrade pip
    #subprocess.call([python_exe, "-m", "ensurepip"])
    #subprocess.call([python_exe, "-m", "pip", "install", "--upgrade", "pip"])

    #subprocess.call([python_exe, "-m", "pip", "install", "--upgrade", "pip"])

    # install required packages
    #subprocess.call([python_exe, "-m", "pip", "install", "pyzenodo3"])
    #subprocess.call([python_exe, "-m", "pip", "install", "python-telegram-bot"])
    
    for install_module in list_of_modules:
        print("ciao")
        #subprocess.call([python_exe, "-m", "pip", "install", "--target=",python_libs, install_module])


    # installed_packages = pkg_resources.working_set
    # installed_packages_list = sorted(["%s==%s" % (i.key, i.version)
    #     for i in installed_packages])
    # print(installed_packages_list)

classes = [
    OBJECT_OT_install_missing_modules,
    ]

def register():
	for cls in classes:
		try:
			bpy.utils.register_class(cls)
		except ValueError as e:
			log.warning('{} is already registered, now unregister and retry... '.format(cls))
			bpy.utils.unregister_class(cls)
			bpy.utils.register_class(cls)

def unregister():
	for cls in classes:
		bpy.utils.unregister_class(cls)

if __name__ == '__main__':
    install_modules()
