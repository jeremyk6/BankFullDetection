# -*- coding: utf-8 -*-
"""
/***************************************************************************
 BankFullDetectionDialog
                                 A QGIS plugin
 Automatic bankfull width detection
                             -------------------
        begin                : 2014-01-20
        copyright            : (C) 2014 by Pierluigi De Rosa
        email                : pierluigi.derosa@gmail.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

import os
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *
from .ui_bankfulldetection import Ui_BankFullDetection
from qgis.core import *
from .tools.XSGenerator import *
from .tools.profiler import ProfilerTool
from .tools.BankElevationDetection import mainFun, hdepth
from shapely.geometry import Polygon


class BankFullDetectionDialog(QDialog, Ui_BankFullDetection):
    def __init__(self,iface):
        QDialog.__init__(self)
        # Set up the user interface from Designer.
        # After setupUI you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect

        self.setupUi(self)
        self.iface = iface
        self.setup_gui()

        self.progressBar.setValue(0)
        
        #general variables
        self.vLayer = None
        self.rLayer = None
        self.ShpFileFolder = None
        self.vlName = None
        
        #~ connections
        #~ self.iface.clicked.connect(self.runXS)
        self.genXSbtn.clicked.connect(self.genXS)
        self.genLbtn.clicked.connect(self.genLine)
        self.buttonProf.clicked.connect(self.runProfile)
        self.ShpSaveBtn.clicked.connect(self.writeLayer)
        self.selXS.clicked.connect(self.runProfileXS)
        self.plotBtn.clicked.connect(self.runValidation)


    def setup_gui(self):
        """ Function to combos creation """
        self.comboVector.clear()
        self.comboDEM.clear()
        curr_map_layers = QgsProject.instance().mapLayers()
        layerRasters = []
        layerVectors = []
        for layer in curr_map_layers.values():
            if layer.type() == QgsMapLayer.VectorLayer:
                layerVectors.append(unicode(layer.name()))
            elif layer.type() == QgsMapLayer.RasterLayer:
                layerRasters.append(unicode(layer.name()))
        self.comboDEM.addItems( layerRasters  )
        self.comboVector.addItems( layerVectors )
        
    def getLayerByName(self,LayerName):
        layer = QgsProject.instance().mapLayersByName(LayerName)[0]
        return layer

    def genLine(self):
        rasterName = self.comboDEM.currentText()
        self.rLayer = self.getLayerByName(rasterName)
        profiler = ProfilerTool()
        profiler.setRaster( self.rLayer )
        XSlayer = self.getLayerByName(str(QCoreApplication.translate( "dialog","Sezioni")))
        points = []
        for feat in XSlayer.getFeatures():
            geom = feat.geometry()
            profileList,e = profiler.doProfile(geom)
            minY = Polygon(profileList).bounds[1]
            dis = 0
            for dis, dept in profileList:
                if dept == minY:
                    break
            pGeom = geom.interpolate(dis)
            if not pGeom.isNull():
                points.append(pGeom.asPoint())
        vl = QgsVectorLayer("LineString", "River line", "memory")
        pr = vl.dataProvider()
        fet = QgsFeature()
        fet.setGeometry( QgsGeometry.fromPolylineXY( points ) )
        pr.addFeatures( [fet] )
        QgsProject.instance().addMapLayer(vl)
            

                
    def genXS(self):
        vectorName = self.comboVector.currentText()
        layer = self.getLayerByName(vectorName)
        step=self.stepXSspin.value()
        width=self.widthXSspin.value()
        #~ message(str(step))
        create_points_secs(layer,step,width)

    def mobileMean(self, l):
        begin = l[0]
        end = l[-1]
        t = []
        for i in range(len(l)):
            if i not in [0,len(l)-1]:
                t.append((l[i-1]+l[i]+l[i+1])/3)
            elif i == 0:
                t.append(l[0])
            else:
                t.append(l[-1])
        return t
                
    def runProfile(self):
        self.progressBar.show()
        
        rasterName = self.comboDEM.currentText()
        self.rLayer = self.getLayerByName(rasterName)
        XSlayer = self.getLayerByName(str(QCoreApplication.translate( "dialog","Sezioni")))
        profiler = ProfilerTool()
        profiler.setRaster( self.rLayer )
        leftPoints = []
        rightPoints = []
        ringPoints = []
        nfeats = int( XSlayer.featureCount() )
        self.progressBar.setMaximum(nfeats)
        i = 0
        self.progressBar.setValue(i)
        nVsteps = self.nVsteps.value()
        minVdep = self.minVdep.value()

        firstSlope = self.chbSlopeLim.isChecked()

        lProfileP = []
        lDept = []
        lGeom = []
        for feat in XSlayer.getFeatures():
            #~ feat = feats[0]
            geom = feat.geometry()
            profileList,e = profiler.doProfile(geom)
            self.iface.mainWindow().statusBar().showMessage( "Elaboro la sez "+str(i+1) )
            dept, err = mainFun(profileList,nVsteps,minVdep,firstSlope,Graph=0)
            if err == 1:
                print("Valeur candidate inférieure à la profondeur min sur %s"%str(i+1))
                nfeats -= 1
            else:
                lProfileP.append(Polygon(profileList))
                lDept.append(dept)
                lGeom.append(geom)
            i = i +1 
            self.progressBar.setValue(i)
        
        '''
        SMOOTHING ZONE
        print("Avant lissage :")
        print(lDept)
        lDept = self.mobileMean(lDept)
        print("Après lissage :")
        print(lDept)
        '''

        for i in range(nfeats):
            minY=lProfileP[i].bounds[1]
            wetArea = lProfileP[i].intersection(hdepth(lProfileP[i],lDept[i]+minY))
            #wetArea = lProfileP[i].intersection(hdepth(lProfileP[i],1+minY))
            startDis = wetArea.bounds[0]
            endDis = wetArea.bounds[2]
            if((lGeom[i].length()-endDis)<1) : endDis = lGeom[i].length() # rustine
            StartPoint = lGeom[i].interpolate( startDis)
            EndPoint = lGeom[i].interpolate(endDis)
            
            leftPoints.append(StartPoint.asPoint() )
            rightPoints.append(EndPoint.asPoint() )
            #~ rightPoints reversing
            ringPoints = leftPoints+rightPoints[::-1]
        
        vl = QgsVectorLayer("Polygon", self.vlName, "memory")
        pr = vl.dataProvider()
        fet = QgsFeature()
        fet.setGeometry( QgsGeometry.fromPolygonXY( [ ringPoints ] ) )
        pr.addFeatures( [fet] )
        QgsProject.instance().addMapLayer(vl)
        
        #check if output file is selected
        shapefilename = self.ShpSaveLine.text()
        if shapefilename == None:
            QMessageBox.critical(self.iface.mainWindow(),QCoreApplication.translate( "message","Error"), QCoreApplication.translate( "message","You have to select output file first"))
        else:
            #~ save vector layer to shapefile
            error = QgsVectorFileWriter.writeAsVectorFormat(vl, shapefilename, "CP1250", vl.sourceCrs(), "ESRI Shapefile")
            if error == QgsVectorFileWriter.NoError:
                QMessageBox.information( self.iface.mainWindow(),"Info",
                str("File %s " %(str(unicode(vl.name())).upper())) + QCoreApplication.translate( "message","succesfully saved"))
        

        
    def writeLayer(self):
        fileName = QFileDialog.getSaveFileName(self, 'Save file', 
                                        "", "Shapefile (*.shp);;All files (*)")
        fileName = os.path.splitext(str(fileName))[0]+'.shp'
        self.ShpSaveLine.setText(fileName)
        base=os.path.basename(fileName)
        os.path.splitext(base)
        self.vlName = os.path.splitext(base)[0]
        
    def runProfileXS(self):
        from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar

        #~ take input parameters fron GUI
        rasterName = self.comboDEM.currentText()
        self.rLayer = self.getLayerByName(rasterName)
        nVsteps = self.nVsteps.value()
        minVdep = self.minVdep.value()
        profiler = ProfilerTool()
        profiler.setRaster( self.rLayer )
        layer = self.iface.activeLayer()
        firstSlope = self.chbSlopeLim.isChecked()
        if layer.selectedFeatureCount() == 1:
            feat = layer.selectedFeatures()[0]
            geomSinXS = feat.geometry()
            profileList,e = profiler.doProfile(geomSinXS)
            canvasPlot = mainFun(profileList,nVsteps,minVdep,firstSlope,Graph=1)
            self.clearLayout(self.layout_plot)
            toolbar = NavigationToolbar(canvasPlot,self.layout_plot.widget())
            #~ self.layout_plot.insertWidget(0, canvasPlot )
            self.layout_plot.addWidget( canvasPlot )
            self.layout_plot.addWidget( toolbar )
            #~ self.setLayout( self.layout_plot)
            
        else:
            QMessageBox.information( self.iface.mainWindow(),"Info",
            str('select feature for ' + str( unicode(layer.name().upper() ) ) ) )

    def runValidation(self):
        from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
        from matplotlib import pyplot
        from descartes.patch import PolygonPatch
        from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
        from statistics import mean, stdev
        
        #~ take input parameters fron GUI
        rasterName = self.comboDEM.currentText()
        self.rLayer = self.getLayerByName(rasterName)
        nVsteps = self.nVsteps.value()
        minVdep = self.minVdep.value()
        profiler = ProfilerTool()
        profiler.setRaster( self.rLayer )
        layer = self.iface.activeLayer()
        firstSlope = self.chbSlopeLim.isChecked()
        nbIter = self.nbExSbox.value()
        if layer.selectedFeatureCount() == 1:
            depts = []
            feat = layer.selectedFeatures()[0]
            for i in range(nbIter):
                profileList,e = profiler.doProfile(feat.geometry())
                dept, err = mainFun(profileList,nVsteps,minVdep,firstSlope,Graph=0)
                if err != 1:
                    depts.append(dept)
                else:
                    depts.append(None)

            """
            Plot
            """
            #fig = pyplot.figure(1, figsize=(4,3), dpi=300)
            fig = pyplot.figure()
            ax = fig.add_subplot(111)
            ax.plot([i for i in range(nbIter)],depts)
            ax.set_title('Detected hydraulic depths')
            
            #~ pyplot.show()
            canvasPlot = FigureCanvas(fig)
            canvasPlot.updateGeometry()
            """
            """
            
            self.clearLayout(self.layout_val)
            toolbar = NavigationToolbar(canvasPlot,self.layout_val.widget())
            #~ self.layout_plot.insertWidget(0, canvasPlot )
            self.layout_val.addWidget( canvasPlot )
            self.layout_val.addWidget( toolbar )
            table = QTableWidget(1,len(depts))
            table.verticalHeader().hide()
            for i in range(len(depts)):
                item = QTableWidgetItem(str(round(depts[i],3)))
                item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                table.setItem(0,i,item)
            mind = round(min(depts),3)
            maxd = round(max(depts),3)
            meand = round(mean(depts),3)
            stdevd = round(stdev(depts),3)
            self.layout_val.addWidget( table )
            save = QPushButton("Save")
            save.clicked.connect(lambda : self.saveCSV(depts))
            self.layout_val.addWidget(save)
            self.layout_val.addWidget( QLabel("Min value : %s\nMax value : %s\nMean : %s\nStDev : %s"%(mind, maxd, meand, stdevd)) )
            #~ self.setLayout( self.layout_plot)
            
        else:
            QMessageBox.information( self.iface.mainWindow(),"Info",
            str('select feature for ' + str( unicode(layer.name().upper() ) ) ) )

    def saveCSV(self, table):
        fname = QFileDialog.getSaveFileName(self, 'Save File', "record.csv","Text files (*.csv)")[0]
        print(fname)
        if fname:
            try:
                file = open(fname,'w')
                csv = ""
                for cell in table:
                    csv += str(round(cell,3))
                    csv += '\n'
                csv = csv[:-1]
                file.write(csv)
                file.close()
            except:
                QMessageBox.critical(self.iface.mainWindow(),"Error","File couldn't be written.")

    def clearLayout(self, layout):
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
                else:
                    self.clearLayout(item.layout())
