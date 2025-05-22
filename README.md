# MegaManager
MegaManager was created out of a desire to make file management across multiple mega accounts more simple, including refreshing the logins for accounts, auto-uploading, and more!

MegaManager runs locally on your machine, and creates a `database.db` which contains all of your sensitive information.  

> **NEVER SHARE DATABASE.DB WITH ANYONE**   
It contains your mega passwords, sharing links, and more. 

This is a design choice so that none of your data is uploaded anywhere - you are responsible for keeping this file safe - and backed up!


# Requirements & Setup
## MegaCMD 
- Download [MegaCMD](https://mega.io/cmd) for your operating system
- Install it

## Python 
- Download [Python](https://www.python.org/downloads/) if you do not already have it installed
- When installing Python (as an administrator), make sure you check the box `Add Python x.x to PATH`
    - This ensures that you can run python related commands from the terminal.
![Python PATH checkbox](https://i.imgur.com/YBO0Rmm.png)
- If you forgot to add it to PATH, you can follow a guide like [this](https://realpython.com/add-python-to-path/), or re-install python!

## MegaManager
- That's this repository! Click `Code -> Download ZIP` at the top right of Github to download the latest version
    - The script contains auto-update functionality, and will prompt you to restart if there has been an update.
- Extract the .zip file somewhere on your computer

## Set up MegaManager
- Open a terminal / command prompt and change directory to where you extracted the .zip from the above step:
    There are a few options for how to do this, the first being the cross-platform option
    - `cd /d D:/Downloads/MegaManager-main`
    - Shift+Right click in Windows Explorer -> `Open command prompt here`
    - Click in the address bar of Windows Explorer -> type `cmd` -> command prompt should launch here
- After this, you should see that your command prompt is in the correct directory
- Run `pip install -r requirements.txt`
    - This installs any required dependencies for the MegaManager to run correctly on your system
    - If you get an error, then try running `python -m ensure-pip` first, this will make sure that `pip` is installed on your system
- Run `python server.py`
    - This starts the server on your PC and can be accessed in any browser.

# Accessing the UI
When the script is running, go to `https://localhost:6342` - this should load the User interface for managing your accounts and files.  
Why :6342? It's `MEGA` on a T9 Keyboard :) 

## Setting up
- Go to /settings.html:
    - Set your path to where MegaCMD is installed
    - Set your date format in the settings, this has a link to how to format it.
    - Set the path(s) to your local files if you have any
    - Save settings at the bottom
- Go to /accounts.html
    - Import a CSV file of your accounts, formatted as below:
    ```
    email,password
    account1@gmail.com,password1
    account+2@gmail.com,password1
    account+3@gmail.com,passw0rd
    account+4@gmail.com,p455w0rd1!
    ```
    - Click `Refresh all`, it should populate with your accounts, their available quotas and more.
- Go to /files.html
    - `Update all details` should fetch your local files as well as storage usage on cloud, if the _exact_ folder name is matched on both local & cloud.
    
