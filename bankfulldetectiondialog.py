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
from .tools.BankElevationDetection import mainFun


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
        self.buttonProf.clicked.connect(self.runProfile)
        self.ShpSaveBtn.clicked.connect(self.writeLayer)
        self.selXS.clicked.connect(self.runProfileXS)


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

        
                
    def genXS(self):
        vectorName = self.comboVector.currentText()
        layer = self.getLayerByName(vectorName)
        step=self.stepXSspin.value()
        width=self.widthXSspin.value()
        #~ message(str(step))
        create_points_secs(layer,step,width)

                
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
        for feat in XSlayer.getFeatures():
            #~ feat = feats[0]
            geom = feat.geometry()
            profileList,e = profiler.doProfile(geom)
            self.iface.mainWindow().statusBar().showMessage( "Elaboro la sez "+str(i+1) )
            startDis, endDis, err = mainFun(profileList,nVsteps,minVdep,Graph=0)
            
            if err == 1:
                print("Valeur candidate inférieure à la profondeur min sur %s"%str(i+1))
            else:
                if((geom.length()-endDis)<1) : endDis = geom.length() # rustine
                StartPoint = geom.interpolate( startDis)
                EndPoint = geom.interpolate(endDis)
                
                leftPoints.append(StartPoint.asPoint() )
                rightPoints.append(EndPoint.asPoint() )
                #~ rightPoints reversing
                ringPoints = leftPoints+rightPoints[::-1]
            i = i +1 
            self.progressBar.setValue(i)
        
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
        if layer.selectedFeatureCount() == 1:
            feat = layer.selectedFeatures()[0]
            geomSinXS = feat.geometry()
            profileList,e = profiler.doProfile(geomSinXS)
            canvasPlot = mainFun(profileList,nVsteps,minVdep,Graph=1)
            self.clearLayout(self.layout_plot)
            toolbar = NavigationToolbar(canvasPlot,self.layout_plot.widget())
            #~ self.layout_plot.insertWidget(0, canvasPlot )
            self.layout_plot.addWidget( canvasPlot )
            self.layout_plot.addWidget( toolbar )
            #~ self.setLayout( self.layout_plot)
            
        else:
            QMessageBox.information( self.iface.mainWindow(),"Info",
            str('select feature for ' + str( unicode(layer.name().upper() ) ) ) )
    
    def clearLayout(self, layout):
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
                else:
                    self.clearLayout(item.layout())
