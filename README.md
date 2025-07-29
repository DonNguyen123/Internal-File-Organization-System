<a href="https://www.buymeacoffee.com/randompers0" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/default-orange.png" alt="Buy Me A Coffee" height="41" width="174"></a>

# Internal-File-Organization-System
This code essentually allow one to access files on drive folders without needing to use external browsers or other apps. To run the code, simply have a basic python installating, and run the python code called "Internal File Organization System.py". Once you have run this, you will most likly seeing something like the image:

![alt text](https://github.com/DonNguyen123/Internal-File-Organization-System/blob/3cb258bd6787f8b25cebdbcf33a842ad17bcf1cb/Example%20Images/Open%20Default.png)

Now it can be stated that from the image above, one can find that there is a right side and the left side. Let us start with the right side, which contains the file tree of the current folder you are in. If you which to change which folder you are in, please click the set root folder on the top left of the GUI, and change it to the folder you need. Afterwards, can click the plus signs next to the folder to show the files, and click on the files to show them on the right section of the GUI. Now note that you may, modify the folders for the GUI only. This means that it only effects the GUI display of the folders/files, and not actual folders/files. For example, if you right click the folder, you will find several options. If the folder is not locked, you have the option to lock or templock or hide the folder. If the folder is locked, you have the option to hide or unlock the folder. An example may be seen in the file below:

<div style="display: flex; flex-wrap: wrap; gap: 10px;">
  <div style="flex: 1 1 200px;">
    <img src="https://github.com/DonNguyen123/Internal-File-Organization-System/blob/e50687bbac2ca95428ab36ab6f27a67514529189/Example%20Images/Example%20Lock.png" style="width: 100%; height: auto; border-radius: 5px;">
  </div>
  <div style="flex: 1 1 200px;">
    <img src="https://github.com/DonNguyen123/Internal-File-Organization-System/blob/b6de0b1b65fad6f423e06919c8121b0b01ae34e6/Example%20Images/Unlocked%20Folders%20With%20Statements.png" style="width: 100%; height: auto; border-radius: 5px;">
  </div>
  <div style="flex: 1 1 200px;">
    <img src="(https://github.com/DonNguyen123/Internal-File-Organization-System/blob/b6de0b1b65fad6f423e06919c8121b0b01ae34e6/Example%20Images/Locked%20Folders.png" style="width: 100%; height: auto; border-radius: 5px;">
  </div>
</div>

Note that in particular, when one locked the folder/file, one will see that a key symbol appeares next to to it, and if one unlocked it, there will be key symbol next to it. When you locked it again, the lock symbol reappears, with the password being the same. Note that a temp lock in this particuar case, is different from a regular lock, as when you unlock it, the password for the lock dissapear, meaning if you want to lock it again, you need to set a new password. Note that you may add optional conditions for unlocking files/folders, such as requring multiple folders to be unlocked before a certain folder/file appear or unlock, is possible. However, you have to go the "statement.txt" folder (which is in the same directory as the main python file) and put in some statements, which may only be in the format as shown below, which each new line being a seperate command. Note that this feature is very expirmental:

![alt text](https://github.com/DonNguyen123/Internal-File-Organization-System/blob/1e6bf3d33cc55bd8acd390dccf84ff01f2f96684/Example%20Images/Statements.png)

For the right side, it can be stated the pdfs, csvs, text files, video and images may be shown. Pdfs in particular, have the option to navigate the pdf by going from the side, and downscrolling. Moreover, for the video and audio, you may have the option to click the create caption button, which generate captions for you to use. You may also download the captions:

<div style="display: flex; flex-wrap: wrap; gap: 10px;">
  <div style="flex: 1 1 200px;">
    <img src="https://github.com/DonNguyen123/Internal-File-Organization-System/blob/b6de0b1b65fad6f423e06919c8121b0b01ae34e6/Example%20Images/Down%20Scroll%20PDF.png" style="width: 100%; height: auto; border-radius: 5px;">
  </div>
  <div style="flex: 1 1 200px;">
    <img src="https://github.com/DonNguyen123/Internal-File-Organization-System/blob/b6de0b1b65fad6f423e06919c8121b0b01ae34e6/Example%20Images/Side%20Scroll%20PDF.png" style="width: 100%; height: auto; border-radius: 5px;">
  </div>
  <div style="flex: 1 1 200px;">
    <img src="(https://github.com/DonNguyen123/Internal-File-Organization-System/blob/b6de0b1b65fad6f423e06919c8121b0b01ae34e6/Example%20Images/CSV%20Example.png" style="width: 100%; height: auto; border-radius: 5px;">
  </div>
  <div style="flex: 1 1 200px;">
    <img src="https://github.com/DonNguyen123/Internal-File-Organization-System/blob/b6de0b1b65fad6f423e06919c8121b0b01ae34e6/Example%20Images/Text%20Example.png" style="width: 100%; height: auto; border-radius: 5px;">
  </div>
  <div style="flex: 1 1 200px;">
    <img src="https://github.com/DonNguyen123/Internal-File-Organization-System/blob/b6de0b1b65fad6f423e06919c8121b0b01ae34e6/Example%20Images/Sound%20Example.png" style="width: 100%; height: auto; border-radius: 5px;">
  </div>
  <div style="flex: 1 1 200px;">
    <img src="https://github.com/DonNguyen123/Internal-File-Organization-System/blob/b6de0b1b65fad6f423e06919c8121b0b01ae34e6/Example%20Images/Video%20Example.png" style="width: 100%; height: auto; border-radius: 5px;">
  </div>
</div>

Note that if you wish to use a better caption model, please change the model in the vosk-model folder, which is located in the same directory as the python code:

![alt text](https://github.com/DonNguyen123/Internal-File-Organization-System/blob/e50687bbac2ca95428ab36ab6f27a67514529189/Example%20Images/Vosk%20Model%20Link.png)

IMPORTANT NOTE: If for some reason there is an VLC error, please change the registary of the VLC player and run the program again and it should work.

