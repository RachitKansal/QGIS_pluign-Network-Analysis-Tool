# -*- coding: utf-8 -*-
"""
/***************************************************************************
 NetworkAnalysisTool
                                 A QGIS plugin
 Network Analysis Tool
                              -------------------
        begin                : 2015-07-01
        git sha              : $Format:%H$
        copyright            : (C) 2015 by rachit, pkar
        email                : rachitkansal@gmail.com
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
from PyQt4.QtCore import *
from PyQt4.QtGui import *
# Initialize Qt resources from file resources.py
import resources_rc
# Import the code for the dialog
from NetworkAnalysisTool_dialog import NetworkAnalysisToolDialog
from qgis.core import *
from qgis.networkanalysis import *
from qgis.gui import *
import os
import sys
import random
import platform
import processing
from operator import itemgetter

class NetworkAnalysisTool:
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
            'NetworkAnalysisTool_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)

        # Create the dialog (after translation) and keep reference
        self.dlg = NetworkAnalysisToolDialog()

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&NetworkAnalysisTool')
        # TODO: We are going to let the user set this up in a future iteration
        self.toolbar = self.iface.addToolBar(u'NetworkAnalysisTool')
        self.toolbar.setObjectName(u'NetworkAnalysisTool')
        self.clickTool = QgsMapToolEmitPoint(self.iface.mapCanvas())

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
        return QCoreApplication.translate('NetworkAnalysisTool', message)


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
            self.iface.addPluginToVectorMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/NetworkAnalysisTool/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'Tool for Network Analysis'),
            callback=self.run,
            parent=self.iface.mainWindow())
        self.initGUI()
        self.defineSignals()


    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginVectorMenu(
                self.tr(u'&NetworkAnalysisTool'),
                action)
            self.iface.removeToolBarIcon(action)
        # remove the toolbar
        del self.toolbar

    def initGUI(self):
        self.dlg.line_comboBox.clear()
        self.dlg.point_comboBox.clear()
        self.dlg.path_comboBox.clear()
        self.dlg.to_comboBox.clear()

    def defineSignals(self):
        self.dlg.run_button.clicked.connect(self.findServiceAreas)
        self.dlg.run2_button.clicked.connect(self.findClosestFacility)
        QObject.connect(self.dlg.select_button, SIGNAL("clicked ( bool )"), self.selectPoint)
        QObject.connect(self.clickTool, SIGNAL("canvasClicked(const QgsPoint &, Qt::MouseButton)"), self.getPoint)
        QObject.connect(self.dlg.clear_button, SIGNAL("clicked ( bool )"), self.clearCanvas)
        QObject.connect(self.dlg.thresh_checkBox, SIGNAL("stateChanged ( int )"), self.toggleThreshBox)

    def silentremove(self, filename):
        try:
            os.remove(filename)
        except OSError:
            pass

    def outputFilePath(self):
        direc = self.plugin_dir
        self.output_file_path = os.path.join(direc, 'network_alloc.shp')
        self.silentremove(os.path.join(direc, 'network_alloc.shp'))
        self.silentremove(os.path.join(direc, 'network_alloc.shx'))
        self.silentremove(os.path.join(direc, 'network_alloc.dbf'))
        self.silentremove(os.path.join(direc, 'network_alloc.prj'))

    def findServiceAreas(self):
        print os.getenv('GISBASE')
        if(platform.system() == 'Darwin'):
            gisbase = os.environ['GISBASE'] = '/Applications/QGIS.app/Contents/MacOS/grass'
        elif(platform.system() == 'Linux'):
            gisbase = os.environ['GISBASE'] = '/usr/lib/grass64'
        elif(platform.system() == 'Windows'):
            gisbase = os.getenv('GISBASE')
        gisdbase = os.path.join(self.plugin_dir, 'grass_db')
        location = 'default'
        mapset = 'user1'
        sys.path.append(os.path.join(os.environ['GISBASE'], "etc", "python"))
        import grass.script as grass
        import grass.script.setup as gsetup
        self.temp_file = gsetup.init(gisbase, gisdbase, location, mapset)
        idx = self.dlg.line_comboBox.currentIndex()
        layer = self.line_layer_list[idx]
        vector_line_filepath = layer.dataProvider().dataSourceUri()
        idx = self.dlg.point_comboBox.currentIndex()
        layer = self.point_layer_list[idx]
        vector_point_filepath = layer.dataProvider().dataSourceUri()
        if(vector_line_filepath.find('|') != -1):
            vector_line_filepath = vector_line_filepath[:vector_line_filepath.find('|')]
        if(vector_point_filepath.find('|') != -1):
            vector_point_filepath = vector_point_filepath[:vector_point_filepath.find('|')]
        print vector_line_filepath
        print vector_point_filepath
        self.outputFilePath()
        self.dlg.progressBar.setEnabled(True)
        self.dlg.progressBar.reset()
        grass.run_command('v.in.ogr', flags = 'o', \
            overwrite = True, \
            dsn = vector_line_filepath, output = 'line')
        print 'opened line'
        self.dlg.progressBar.setValue(round((100.0/6.0)*1))
        grass.run_command('v.in.ogr', flags = 'o', \
            overwrite = True, \
            dsn = vector_point_filepath, output = 'points')
        print 'opened point'
        grass.run_command('g.region', \
            vect = 'line')
        self.dlg.progressBar.setValue(round((100.0/6.0)*2))
        self.thresh = self.dlg.thresh_spinBox.value()
        self.ccats_low = self.dlg.ccats_low_spinBox.value()
        self.ccats_high = self.dlg.ccats_high_spinBox.value()
        clist = range(self.ccats_low, self.ccats_high + 1)
        grass.run_command('v.net', \
            input = 'line', \
            points = 'points', \
            output = 'network', \
            overwrite = True, \
            operation = 'connect', \
            thresh = self.thresh)
        print 'done v.net'
        self.dlg.progressBar.setValue(round((100.0/6.0)*3))
        grass.run_command('v.db.connect', \
            map = 'network', \
            table = 'point', \
            layer = 2)
        print 'done v.db.connect'
        self.dlg.progressBar.setValue(round((100.0/6.0)*4))
        grass.run_command('v.net.alloc', \
            overwrite = True, \
            input = 'network', \
            output = 'network_alloc', \
            ccats = ','.join(str(e) for e in clist))
        print 'done v.net.alloc'
        self.dlg.progressBar.setValue(round((100.0/6.0)*5))
        grass.run_command('v.out.ogr', \
            overwrite = True, \
            input = 'network_alloc', \
            dsn = self.output_file_path)
        print 'done'
        self.dlg.progressBar.setValue(round((100.0/6.0)*6))
        QMessageBox.information(self.dlg, "Done", "Output_File_Path: %s" % (self.output_file_path))
        self.dlg.progressBar.setEnabled(False)
        hull_file_output = processing.runalg("qgis:convexhull",self.output_file_path,"cat",1,None)
        hull_layer = self.iface.addVectorLayer(hull_file_output['OUTPUT'], 'hull', 'ogr')
        my_crs = self.iface.mapCanvas().mapRenderer().destinationCrs()
        layer = self.iface.addVectorLayer(self.output_file_path, 'network_alloc', 'ogr')
        renderer = QgsCategorizedSymbolRendererV2('cat', self.colorCategorize(layer, 'cat'))
        layer.setCrs(my_crs)
        hull_layer.setCrs(my_crs)
        layer.setRendererV2(renderer)
        canvas = self.iface.mapCanvas()
        canvas.setExtent(layer.extent())
        layer.triggerRepaint()
        canvas.refresh()
        os.remove(self.temp_file)

    def findClosestFacility(self):
        if(self.selected_point == False):
            QMessageBox.warning(self.dlg, "Info", "Select A Start Point!!")
            return
        else:
            self.selected_point = False
        self.iface.mapCanvas().setMapUnits(0)
        self.closest_dist_list = []
        self.closest_idx_list = []
        thresh_state = self.dlg.thresh_checkBox.isChecked()
        if(thresh_state):
            self.thesh_dist = self.dlg.dist_SpinBox.value()
        idx = self.dlg.path_comboBox.currentIndex()
        vl = self.line_layer_list[idx]
        idx = self.dlg.to_comboBox.currentIndex()
        layer = self.point_layer_list[idx]
        # self.outputFilePath()
        director = QgsLineVectorLayerDirector(vl, -1, '', '', '', 3)
        properter = QgsDistanceArcProperter()
        director.addProperter(properter)
        crs = self.iface.mapCanvas().mapRenderer().destinationCrs()
        builder = QgsGraphBuilder(crs)

        point_list=[]
        pStart = QgsPoint(self.x, self.y)
        point_list.append(pStart)
        
        features = layer.getFeatures()
        for fet in features:
            geom = fet.geometry()
            if geom.type() == QGis.Point:
                point_list.append(geom.asPoint())
        
        tiedPoints = director.makeGraph(builder, point_list)
        graph = builder.graph()
        minDist=-1
        minp=[]
        minIndex=-1
        self.dlg.progressBar_2.reset()
        for i in range(1,len(point_list)):
            print round((float(i)/(len(point_list) - 1))*100), '%'
            self.dlg.progressBar_2.setValue(round((float(i)/(len(point_list) - 1))*100))
            tStart = tiedPoints[0]
            tStop = tiedPoints[i]
            idStart = graph.findVertex(tStart)
            idStop = graph.findVertex(tStop)
            tree=[]
            cost=[]
            (tree, cost) = QgsGraphAnalyzer.dijkstra(graph, idStart, 0)
            if tree[idStop] == -1:
                print "Path not found"
            else:
                p = []
                curPos = idStop
                while curPos != idStart:
                    p.append(graph.vertex(graph.arc(tree[curPos]).inVertex()).point())
                    curPos = graph.arc(tree[curPos]).outVertex()
                p.append(tStart)
                dist = cost[idStop]
                if(thresh_state and dist < self.thesh_dist):
                    self.closest_dist_list.append(dist)
                    self.closest_idx_list.append(i)
                if (minDist==-1):
                    minDist=dist
                    mintree=p
                    minIndex=i
            
                if (dist<minDist):
                    minDist=dist
                    minp=p
                    minIndex=i
                print i
                print dist
                print minDist
        print minp

        if(thresh_state):
            output_text = []
            layer.setSelectedFeatures([x - 1 for x in self.closest_idx_list])
            print len(self.closest_idx_list)
            for i in range(0, len(self.closest_idx_list)):
                string = "Distance: %f m\nCategory Number: %d" % (self.closest_dist_list[i], self.closest_idx_list[i])
                output_text.append(string)
            QMessageBox.information(self.dlg, "Done", '\n'.join(output_text))
            return

        self.rb = QgsRubberBand(self.iface.mapCanvas())
        self.rb.setColor(Qt.red)
        for pnt in minp:
            self.rb.addPoint(pnt)
        print minIndex
        layer.setSelectedFeatures([minIndex-1])
        box = layer.boundingBoxOfSelected()
        self.iface.mapCanvas().setExtent(box)
        self.iface.mapCanvas().refresh()
        QMessageBox.information(self.dlg, "Done", "Distance: %f m\nCategory Number: %d" % (minDist, minIndex))

    def selectPoint(self):
        self.iface.mapCanvas().setMapTool(self.clickTool)

    def getPoint(self, point):
        self.clearCanvas()
        self.selected_point = True
        self.x=point.x()
        self.y=point.y()
        print self.x
        self.iface.mapCanvas().unsetMapTool(self.clickTool)
        self.m = QgsVertexMarker(self.iface.mapCanvas())
        self.m.setCenter(QgsPoint(self.x, self.y))

    def clearCanvas(self):
        try:
            self.iface.mapCanvas().scene().removeItem(self.m)
        except AttributeError:
            pass
        try:
            self.iface.mapCanvas().scene().removeItem(self.rb)
        except AttributeError:
            pass

    def toggleThreshBox(self):
        thresh_state = self.dlg.thresh_checkBox.isChecked()
        if(thresh_state):
            self.dlg.dist_SpinBox.setEnabled(True)
        else:
            self.dlg.dist_SpinBox.setEnabled(False)

    # def browseFile(self):
    #     fname = QFileDialog.getExistingDirectory(None, "Select Directory", self.plugin_dir)
    #     self.dlg.output_dir_text_edit.setText(fname)

    # def toggleOutputFile(self):
    #     out_state = self.dlg.save_output_checkBox.isChecked()
    #     if(out_state):
    #         self.dlg.output_dir_text_edit.setEnabled(True)
    #         self.dlg.output_dir_browse_button.setEnabled(True)
    #     else:
    #         self.dlg.output_dir_text_edit.setEnabled(False)
    #         self.dlg.output_dir_browse_button.setEnabled(False)

    def uniqueValues(self, layer, attr):
        values = []
        fieldIndex = layer.dataProvider().fieldNameIndex(attr)
        feats = layer.getFeatures()
        for feat in feats:
            if feat.attributes()[fieldIndex] not in values:
                values.append(feat.attributes()[fieldIndex])
        return values

    def colorCategorize(self, layer, attr):
        fieldIndex = layer.dataProvider().fieldNameIndex(attr)
        print fieldIndex
        # unique_values = self.uniqueValues(layer, attr)
        unique_values = layer.uniqueValues(fieldIndex)
        print unique_values
        categories = []
        for value in unique_values:
            symbol = QgsSymbolV2.defaultSymbol(1)
            symbol.setColor(QColor(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)))
            # symbol.setWidth(0.3)
            category = QgsRendererCategoryV2(value, symbol, str(value))
            categories.append(category)
        return categories

    def run(self):
        """Run method that performs all the real work"""
        self.initGUI()
        self.selected_point = False
        layermap = QgsMapLayerRegistry.instance().mapLayers()
        self.line_layer_list = []
        self.line_layer_names = []
        self.point_layer_list = []
        self.point_layer_names = []
        for name, layer in layermap.iteritems():
            if(layer.type() == QgsMapLayer.VectorLayer):
                if(layer.geometryType() == 0):
                    self.point_layer_list.append(layer)
                    self.point_layer_names.append(layer.name())
                elif(layer.geometryType() == 1):
                    self.line_layer_list.append(layer)
                    self.line_layer_names.append(layer.name())
        self.dlg.line_comboBox.addItems(self.line_layer_names)
        self.dlg.point_comboBox.addItems(self.point_layer_names)
        self.dlg.path_comboBox.addItems(self.line_layer_names)
        self.dlg.to_comboBox.addItems(self.point_layer_names)
        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()
        self.clearCanvas()
        # See if OK was pressed
        if result:
            # Do something useful here - delete the line containing pass and
            # substitute with your code.
            pass
