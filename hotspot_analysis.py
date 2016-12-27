# -*- coding: utf-8 -*-
"""
/***************************************************************************
 HotspotAnalysis
                                 A QGIS plugin
 This plugin generates data needed for hotspot Analysis
                              -------------------
        begin                : 2016-06-19
        git sha              : $Format:%H$
        copyright            : (C) 2016 by Stanly Shaji, Arunkumar / Politecnico Di Milano
        email                : stanly.shaji@mail.polimi.it
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
from PyQt4.QtCore import QSettings, QTranslator, qVersion, QCoreApplication
from PyQt4.QtGui import QAction, QIcon, QFileDialog, QComboBox, QFrame, QLineEdit, QMessageBox
from qgis.core import QgsMapLayerRegistry, QgsVectorLayer
# Initialize Qt resources from file resources.py
import resources
import resources_rc
# Import the code for the dialog
from hotspot_analysis_dialog import HotspotAnalysisDialog
import os.path

import pysal
from pysal.esda.getisord import *
from pysal.weights.Distance import DistanceBand

import numpy
import sys

from osgeo import ogr, gdal 


class NullWriter(object):
    def write(self, value): pass

sys.stdout = sys.stderr = NullWriter()

class HotspotAnalysis:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'HotspotAnalysis_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)

        # Create the dialog (after translation) and keep reference
        self.dlg = HotspotAnalysisDialog()

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&Hotspot Analysis')
        # TODO: We are going to let the user set this up in a future iteration
        self.toolbar = self.iface.addToolBar(u'HotspotAnalysis')
        self.toolbar.setObjectName(u'HotspotAnalysis')
        # Load output directory path
        self.dlg.lineEdit.clear()
        self.dlg.pushButton.clicked.connect(self.select_output_file)
        self.clear_ui()

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('HotspotAnalysis', message)


    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/HotspotAnalysis/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'Generate Data for Hotspot Analysis'),
            callback=self.run,
            parent=self.iface.mainWindow())
            
    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&Hotspot Analysis'),
                action)
            self.iface.removeToolBarIcon(action)
        # remove the toolbar
        del self.toolbar
        
    def select_output_file(self):
        """Selects the output file directory """
        filename = QFileDialog.getSaveFileName(self.dlg, "Select output path directory ")
        self.dlg.lineEdit.setText(filename)
        
    def optimizedThreshold(self,checked):
        """Settings for Optimized threshold"""
        if checked == True:
            self.dlg.lineEdit_minT.setEnabled(True)
            self.dlg.lineEdit_maxT.setEnabled(True)
            self.dlg.lineEdit_dist.setEnabled(True)
            self.dlg.lineEditThreshold.setEnabled(False)
            self.dlg.lineEditThreshold.clear()
            self.dlg.label_threshold.setEnabled(False)
            self.dlg.label_7.setEnabled(True)
            self.dlg.label_8.setEnabled(True)
            self.dlg.label_9.setEnabled(True)
        
        else:
            threshold = self.dlg.lineEditThreshold.text()
            self.dlg.lineEdit_minT.setEnabled(False)
            self.dlg.lineEdit_minT.clear()
            self.dlg.lineEdit_maxT.clear()
            self.dlg.lineEdit_dist.clear()
            self.dlg.lineEdit_maxT.setEnabled(False)
            self.dlg.lineEdit_dist.setEnabled(False)
            self.dlg.lineEditThreshold.setEnabled(True)
            self.dlg.label_threshold.setEnabled(True)
            self.dlg.label_7.setEnabled(False)
            self.dlg.label_8.setEnabled(False)
            self.dlg.label_9.setEnabled(False)
        
    def clear_ui(self):
        """Clearing the UI for new operations"""
        self.dlg.comboBox.clear()
        self.dlg.lineEdit.clear()
        self.dlg.lineEditThreshold.clear()
        self.dlg.comboBox_C.clear()
        self.dlg.lineEditThreshold.setEnabled(True)
        self.dlg.checkBox.setChecked(False)
        self.dlg.checkBox_2.setChecked(False)
        self.dlg.lineEdit_minT.setEnabled(False)
        self.dlg.lineEdit_maxT.setEnabled(False)
        self.dlg.lineEdit_dist.setEnabled(False)
        self.dlg.lineEdit_minT.clear()
        self.dlg.lineEdit_maxT.clear()
        self.dlg.lineEdit_dist.clear()
        self.dlg.label_7.setEnabled(False)
        self.dlg.label_8.setEnabled(False)
        self.dlg.label_9.setEnabled(False)
        
    def clear_fields(self):
        """Clearing the fields when layers are changed"""
        self.dlg.comboBox_C.clear()
        
            
    def write_file(self,filename,sf,lg_star,field_C,C,layerName,inLayer,inDataSource,threshold1):
        """Writing the output shapefile into the mentioned directory"""
        outDriver = ogr.GetDriverByName("ESRI Shapefile")
        
        layerName=layerName.split('.')
        layerName.pop()
        layerName='.'.join(layerName)	
        
        outShapefile = filename+".shp"
        
        # Remove eventually alrady exisiting output 
        if os.path.exists(outShapefile):
            outDriver.DeleteDataSource(outShapefile)
            
        # Create the output shapefile
        outDataSource = outDriver.CreateDataSource(outShapefile)
        outLayer = outDataSource.CreateLayer("output",  inLayer.GetSpatialRef(), inLayer.GetLayerDefn().GetGeomType())
    
        # Add input Layer Fields to the output Layer
        inLayerDefn = inLayer.GetLayerDefn()
        for i in range(0, inLayerDefn.GetFieldCount()):
            fieldDefn = inLayerDefn.GetFieldDefn(i)
            outLayer.CreateField(fieldDefn)

        ##
        # Add additional fields - for more types other than Strings take a look at http://pcjericks.github.io/py-gdalogr-cookbook/layers.html#create-a-new-shapefile-and-add-data
        ##

        # Add empty field to store Pysal results
        Z_field = ogr.FieldDefn("Z-score", ogr.OFTReal)
        Z_field.SetWidth(15)
        Z_field.SetPrecision(10)
        outLayer.CreateField(Z_field)

        p_field = ogr.FieldDefn("p-value", ogr.OFTReal)
        p_field.SetWidth(15)
        p_field.SetPrecision(10)
        outLayer.CreateField(p_field)

        # Get the output Layer's Feature Definition
        outLayerDefn = outLayer.GetLayerDefn()
        # Get the input Layer's Feature Definition
        inLayerDefn  = inLayer.GetLayerDefn()

        # Add features to the ouput Layer
        for i in range(0, inLayer.GetFeatureCount()):
            # Get the input Feature
            inFeature = inLayer.GetFeature(i)
            # Create output Feature
            outFeature = ogr.Feature(outLayerDefn)
            # Add field values from input Layer
            for j in range(0, inLayerDefn.GetFieldCount()):
                outFeature.SetField(outLayerDefn.GetFieldDefn(j).GetNameRef(), inFeature.GetField(j))
            # Set geometry
            geom = inFeature.GetGeometryRef()
            outFeature.SetGeometry(geom)
            # Add Z-scores and p-values to their field column 
            outFeature.SetField("Z-score", lg_star.z_sim[i])
            outFeature.SetField("p-value", lg_star.p_z_sim[i]*2)
            # Add new feature to output Layer
            outLayer.CreateFeature(outFeature)

        # Close DataSources
        inDataSource.Destroy()
        outDataSource.Destroy()
    
        
        self.success_msg(threshold1)
        new_layer = self.iface.addVectorLayer(filename+".shp", str(os.path.basename(os.path.normpath(filename))), "ogr")
        if not new_layer:
            QMessageBox.information(self.dlg, self.tr("New Layer"),self.tr("Layer Cannot be Loaded"),QMessageBox.Ok)
        self.clear_ui() 
        
    def load_comboBox(self,layers):
        """Load the fields into combobox when layers are changed"""
        selectedLayerIndex = self.dlg.comboBox.currentIndex()
        selectedLayer = layers[selectedLayerIndex]
        fieldnames = []
        fieldnames = [field.name() for field in selectedLayer.pendingFields()]
        self.clear_fields()
        self.dlg.comboBox_C.addItems(fieldnames)
        (path,layer_id)=selectedLayer.dataProvider().dataSourceUri().split('|')
        thresh = pysal.min_threshold_dist_from_shapefile(path)
        self.dlg.lineEditThreshold.setText(str(int(thresh)))
        
    def error_msg(self):
        """Message to report missing fields"""
        self.clear_ui()
        QMessageBox.warning(self.dlg.show(), self.tr("HotspotAnalysis:Warning"),self.tr("Please specify input fields properly"),QMessageBox.Ok)
        
    def success_msg(self,distance):
        """Message to report succesful file creation"""
        QMessageBox.information(self.dlg, self.tr("HotspotAnalysis:Success"),self.tr("File is generated Succesfully (Distance used = "+ str(distance)+")"),QMessageBox.Ok)
        
    def validator(self):
        """Validator to Check whether the inputs are given properly"""
        if ((self.dlg.checkBox.isChecked() == 0 and self.dlg.lineEditThreshold.text() != "") or (self.dlg.checkBox.isChecked() == 1 and (self.dlg.lineEdit_dist.text() != "" and self.dlg.lineEdit_maxT.text() != "" and self.dlg.lineEdit_minT.text() != "" ))) and self.dlg.lineEdit.text()!="":
            return 1
        else:
            return 0
            
    def run(self):
        """Run method that performs all the real work"""
        self.clear_ui() 
        layers_list = []
        layers_shp = []
        #Show the shapefiles in the COmboBox
        layers = self.iface.legendInterface().layers()
        if len(layers)!=0:#checklayers exist in the project
            for layer in layers:
                myfilepath= layer.dataProvider().dataSourceUri() #directory including filename
                (myDirectory,nameFile) = os.path.split(myfilepath)#splitting into directory and filename
                if (".shp" in nameFile):
                    layers_list.append(layer.name())
                    layers_shp.append(layer)
            self.dlg.comboBox.addItems(layers_list)#adding layers to comboBox
            selectedLayerIndex = self.dlg.comboBox.currentIndex()
            selectedLayer = layers_shp[selectedLayerIndex]
            fieldnames = [field.name() for field in selectedLayer.pendingFields()]#fetching fieldnames of layer
            self.clear_fields()
            self.dlg.comboBox_C.addItems(fieldnames)
            self.dlg.comboBox.activated.connect(lambda:self.load_comboBox(layers_shp))
            self.dlg.comboBox.currentIndexChanged.connect(lambda:self.load_comboBox(layers_shp))
            self.dlg.checkBox.toggled.connect(self.optimizedThreshold)#checkbox toggle event
            self.load_comboBox(layers_shp)

        
        # show the dialog
            self.dlg.show()		
        # Run the dialog event loop
            result = self.dlg.exec_()
        # See if OK was pressed and fields are not empty
            if result and (self.validator()==1):
                selectedLayerIndex = self.dlg.comboBox.currentIndex()
                selectedLayer = layers_shp[selectedLayerIndex]
                layerName = selectedLayer.dataProvider().dataSourceUri()
                C = selectedLayer.fieldNameIndex(self.dlg.comboBox_C.currentText())
                filename = self.dlg.lineEdit.text()
                (path,layer_id) = layerName.split('|')
            
                
                inDriver = ogr.GetDriverByName("ESRI Shapefile")
                inDataSource = inDriver.Open(path, 0)
                inLayer = inDataSource.GetLayer()
                               
                t = ()
                for feature in inLayer:
                    geometry = feature.GetGeometryRef()
                    xy= (geometry.GetX(), geometry.GetY())
                    t = t+ (xy,)
                
                u=[] 
                for i in range(0, inLayer.GetFeatureCount()):
                    geometry = inLayer.GetFeature(i)
                    u.append(geometry.GetField(C))    
                    
                y = numpy.array(u)#point attribute
                               
                if self.dlg.checkBox.isChecked() == 0:#if threshold is given
                    threshold1 = int(self.dlg.lineEditThreshold.text())
                else:#if user needs to optimize threshold
                    mx_moran = -1000.0
                    mx_i = -1000.0
                    minT = int(self.dlg.lineEdit_minT.text())
                    maxT = int(self.dlg.lineEdit_maxT.text())
                    dist = int(self.dlg.lineEdit_dist.text())
                    for i in range(minT, maxT, dist):
                        w = DistanceBand(t,threshold=i, p=2, binary=False)
                        moran = pysal.Moran(y, w)
                            #print moran.z_norm
                        if moran.z_norm > mx_moran:
                            mx_i = i
                            mx_moran = moran.z_norm
                    threshold1 = int(mx_i)
                w = DistanceBand(t,threshold1, p=2, binary=False)
                if self.dlg.checkBox_2.isChecked() == 1:
					w_type = "r"
                else:
					w_type = "B"
                lg_star = G_Local(y,w,transform='B',star=True)
                self.write_file(filename,inLayer,lg_star,self.dlg.comboBox_C.currentText(),C,layerName, inLayer, inDataSource, threshold1)
                # assign the style to the output layer on QGIS 
                self.iface.activeLayer().loadNamedStyle(os.path.dirname(__file__) + "/hotspots_class.qml")
            elif result and (self.validator()==0):
                self.error_msg()
            else:
                self.clear_ui()
                pass
              
                     
