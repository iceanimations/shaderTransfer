import site
site.addsitedir(r"R:\Pipe_Repo\Users\Qurban\utilities")
from uiContainer import uic
from PyQt4.QtCore import *
from PyQt4.QtGui import *
import qtify_maya_window as qtfy
import os.path as osp
import pymel.core as pc
import maya.cmds as mc

Form, Base = uic.loadUiType(r'%s\\ui\\uiCombo.ui' % osp.dirname(osp.dirname(__file__)))
class Window(Form, Base):
    def __init__(self, parent = qtfy.getMayaWindow()):
        super(Window, self).__init__(parent)
        self.setupUi(self)
        
        self.sourceObject = None
        self.targetObjects = []
        
        self.transferButton.clicked.connect(self.transfer)
        self.transferPolicyBox.currentIndexChanged.connect(self.handleComboBox)
        self.addSourceButton.clicked.connect(self.addSourceObjects)
        self.addTargetButton.clicked.connect(self.addTargetObjects)
        self.removeAllButton.clicked.connect(self.removeAll)
        self.removeSelectionButton.clicked.connect(self.removeSelection)
        self.closeButton.clicked.connect(self.close)
        self.progressBar.hide()
        self.mainProgressBar.hide()
        self.bigProgressBar.hide()
        self.sBar = self.statusBar()
        self.handleComboBox()

        #update the database
        site.addsitedir(r'R:/pipe_Repo/users/Qurban')
        import appUsageApp
        appUsageApp.updateDatabase('shaderTransfer')
        
    def closeEvent(self, event):
        self.deleteLater()
    
    def setStatus(self, msg):
        '''sets the message for the status bar of main window'''
        self.sBar.showMessage(msg, 3000)
        
    def addSourceObjects(self):
        '''adds source objects to the list'''
        if not self.isSelected():
            self.msgBox(self, msg = 'The system can not find any selection in the current scene',
                   icon = QMessageBox.Warning)
            return
        objs = self.selectedObjects(self.transferPolicy)
        if objs:
            self.sourceBox.setText(objs[0])
            self.sourceObject = objs[0]
        else: self.msgBox(self, msg = 'Selected object does not match the selected policy',
                     icon = QMessageBox.Warning)

    def addTargetObjects(self):
        '''adds the target objects to list'''
        if not self.isSelected():
            self.msgBox(self, msg = 'The system can not find any selection in the current scene',
                   icon = QMessageBox.Warning)
            return
        objects = self.selectedObjects(self.transferPolicy)
        if objects:
            for obj in objects:
                item = QListWidgetItem()
                item.setText(obj)
                self.targetBox.addItem(item)
                self.targetObjects.append(obj)
        else:
            self.msgBox(self, msg = 'Selected object(s) type does not match the selected policy',
                   icon = QMessageBox.Warning)
    
    def removeAll(self):
        '''removes all the added objects from both lists'''
        self.targetBox.clear()
        del self.targetObjects[:]
        
    def removeSelection(self):
        '''removes the selected objects from the both lists'''
        for selectedItem in self.targetBox.selectedItems():
            self.targetObjects.remove(str(self.targetBox.takeItem(self.targetBox.indexFromItem(selectedItem).row()).text()))

    def handleComboBox(self):
        '''handles when the current index of the comboBox is changed'''
        text = str(self.transferPolicyBox.currentText())
        self.removeAll()
        self.sourceBox.clear()
        self.sourceObject = None
        if text == 'Single to Single':
            self.setStatus('Selection type should be Mesh')
            self.addSourceButton.setText('Add Source Mesh')
            self.addTargetButton.setText('Add Target Mesh')
            self.transferPolicy = 'ctoc'
        if text == 'Set to Set':
            self.setStatus('Selection type should be Set')
            self.addSourceButton.setText('Add Source Set')
            self.addTargetButton.setText('Add Target Set')
            self.transferPolicy = 'stos'
            
    def transfer(self):
        '''calls the appropraite function to transfer the shaders'''
        if not self.sourceBox.text():
            self.msgBox(self, msg = 'Source object is not added to the field',
                   icon = QMessageBox.Warning)
            return
        if not self.targetBox.count():
            self.msgBox(self, msg = 'Target objects are not added to list',
                   icon = QMessageBox.Warning)
            return
        badFaces = {} # number of faces is different in source and target meshes
        badLength = [] # number of meshes is different in source and target sets
        if self.transferPolicy == 'ctoc':
            badFaces.update(self.singleToSingle(self.sourceObject, self.targetObjects))
        if self.transferPolicy == 'stos':
            faces, length = self.stosCaller(self.sourceObject, self.targetObjects)
            badFaces.update(faces)
            badLength += length

        if badFaces:
            keys = badFaces.keys()
            nKeys = len(keys)
            detail = 'Face count does not match for the following Meshes:\n'
            for i in range(nKeys):
                detail += str(i+1) + ': '+ keys[i] +' and '+ badFaces[keys[i]] +'\n'
            self.msgBox(self, msg = 'Number of faces does not match in the Meshes',
                   details = detail, icon = QMessageBox.Warning)
        if badLength:
            detail = 'Following source meshes not found in target set:\n'
            for i in range(len(badLength)):
                detail += str(i+1) + ': '+ badLength[i] +'\n'
            self.msgBox(self, msg = 'Number of meshes in Target sets do not match the number of meshes in the Source Set',
                   icon = QMessageBox.Warning, details = detail)
        self.bigProgressBar.hide()
        self.bigProgressBar.setValue(0)
        self.mainProgressBar.hide()
        self.mainProgressBar.setValue(0)
        self.progressBar.hide()
        self.progressBar.setValue(0)
            
    def singleToSingle(self, source, targets):
        # list the shading engines connected to the source mesh
        
        badFaces = {}
        source = pc.PyNode(source); targets = [pc.PyNode(target) for target in targets]
        sourceFaces = source.numFaces()
        shGroups = set(source.connections(type=pc.nt.ShadingEngine))
        
        sgLen = len(shGroups)
        targLen = len(targets)
        if sgLen > 1:
            self.bigProgressBar.show()
        self.bigProgressBar.setMaximum(sgLen)
        
        if targLen > 1:
            self.mainProgressBar.show()
            self.mainProgressBar.setMaximum(targLen)
        
        c = 0
        targetMembers = []
        for sg in shGroups:
            sgMembers = mc.sets(str(sg), q = True)
            if sgMembers:
                temp = []
                for member in sgMembers:
                    try:
                        pyNode = pc.PyNode(member)
                        temp.append(pyNode)
                    except pc.MayaAttributeError:
                        pass
                sgMembers[:] = temp
                memLen = len(sgMembers)
                if source in sgMembers:
                    pc.sets(sg, e = 1, fe=targets)
                    for trg in targets:
                        self.transferUVs(source, trg)
                    return badFaces
                del targetMembers[:]
                
                if memLen > 1 and targLen < 2:
                    self.progressBar.show()
                    self.progressBar.setMaximum(memLen)
                
                c2 = 0
                for targ in targets:
                    if sourceFaces != targ.numFaces():
                        badFaces[str(source)] = str(targ)
                        continue
                    
                    c3 = 0
                    for mem in sgMembers:
                        meshAndFace = str(mem).split('.')
                        if len(meshAndFace) == 1:
                            continue
                        if pc.objExists(mem) and mem.node() == source:
                            item = '.'.join([str(targ), meshAndFace[-1]])
                            if pc.objExists(item):
                                targetMembers.append(item)
                        c3 += 1
                        self.progressBar.setValue(c3)
                        qApp.processEvents()
                        
                    c2 += 1
                    self.mainProgressBar.setValue(c2)
                    qApp.processEvents()
                    self.transferUVs(source, targ)
                if targetMembers:
                    pc.sets(sg, e=1, fe=targetMembers)
                c += 1
                self.bigProgressBar.setValue(c)
                qApp.processEvents()
            
        # transfer UVs
#         if self.uvButton.isChecked():
#             for targ in targets:
#                 self.transferUVs(source, targ)
        return badFaces
    
    def stosCaller(self, sourceSet, targetSets):
        '''accpts two sets and gets the meshes from those sets'''
        sourceSet = pc.PyNode(sourceSet)
        badFaces = {} # when the number of faces is is different in the source and target meshes
        badLength = [] # when the number of meshes is different in the source and target sets
        sourceMeshes = []
        if type(sourceSet) == pc.nt.Transform:
            sourceSet = sourceSet.getChildren()
        else:
            sourceSet = sourceSet.dsm.inputs()
        for transform in sourceSet:
            mesh = transform.getShape()
            if type(mesh) == pc.nt.Mesh: sourceMeshes.append(mesh)
        sourceLength = len(sourceMeshes)
        if sourceLength > 1:
            self.mainProgressBar.show()
        if len(targetSets) > 1:
            self.bigProgressBar.show()
        self.bigProgressBar.setMaximum(len(targetSets))
        self.mainProgressBar.setMaximum(sourceLength)
        c1 = 0
        for _set in targetSets:
            _set = pc.PyNode(_set)
            targetMeshes = []
            #get the meshes from the transform nodes
            if type(_set) == pc.nt.Transform:
                _set = _set.getChildren()
            else:
                _set = _set.dsm.inputs()
            for transform in _set:
                mesh = transform.getShape()
                if type(mesh) ==  pc.nt.Mesh: targetMeshes.append(mesh)
            # for each mesh in source set, transfer the shader to corresponding mesh in the target set
            c2 = 0
            for i in range(sourceLength):
                print i
                src = sourceMeshes[i]
                # get the post fix name of the mesh in the set
                try:
                    targ = targetMeshes[i]
                    # check if the number of faces is different in the corresponding meshes
                    if len(src.faces) != len(targ.faces):
                        badFaces[src] = targ
                        continue
                    #transfer the shaders
                    self.singleToSingle(src, [targ])
                except IndexError: badLength.append(src)
                c2 += 1
                self.mainProgressBar.setValue(c2)
                qApp.processEvents()
            c1 += 1
            self.bigProgressBar.setValue(c1)
            qApp.processEvents()
        self.bigProgressBar.hide()
        self.mainProgressBar.hide()
        return badFaces, badLength
            
    def isSelected(self):
        '''
        @return True, if selection exists in the current scene
        '''
        if pc.ls(sl=True, type=pc.nt.ObjectSet) or pc.ls(sl=True, dag=True, type=pc.nt.Mesh): return True
        return False
        
    def selectedObjects(self, policy):
        '''returns the list of selected objects from the scene'''
        if policy == 'stos':
            return [str(obj) for obj in pc.ls(sl=True, type=[pc.nt.ObjectSet, pc.nt.Transform])]
        if policy == 'ctoc':
            return [str(obj) for obj in pc.ls(sl=True, dag=True, type='mesh')]
    
    def transferUVs(self, source, target):
        '''
        transfers uv from source mesh to target mesh
        '''
        pc.polyTransfer(target, ao = source, uv=True)

    def msgBox(self, parent, msg = None, btns = QMessageBox.Ok,
               icon = None, ques = None, details = None):
        '''
        dispalys the warnings
        @params:
                args: a dictionary containing the following sequence of variables
                {'msg': 'msg to be displayed'[, 'ques': 'question to be asked'],
                'btns': QMessageBox.btn1 | QMessageBox.btn2 | ....}
        '''
        if msg:
            mBox = QMessageBox(self)
            mBox.setWindowModality(Qt.ApplicationModal)
            mBox.setWindowTitle('Shader Transfer')
            mBox.setText(msg)
            if ques:
                mBox.setInformativeText(ques)
            if icon:
                mBox.setIcon(icon)
            if details:
                mBox.setDetailedText(details)
            mBox.setStandardButtons(btns)
            buttonPressed = mBox.exec_()
            return buttonPressed