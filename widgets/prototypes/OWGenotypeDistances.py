"""<name>Genotype Distances</name>
"""

from OWWidget import *
import OWGUI
from OWItemModels import PyListModel
import Orange

from collections import defaultdict

def separate_by(data, separate, ignore=[], consider=None, add_empty=True):
    """
    data - the data - annotations are saved in the at.attributes
    annotatitions: keys of at.attributes  by which to separate
    ignore: ignore values of these annotations
    consider: consider only these annotations
    """
    ignore = set(ignore)

    annotations = [ at.attributes for at in data.domain.attributes ]

    all_values = defaultdict(set)
    for a in annotations:
        for k,v in a.iteritems():
            all_values[k].add(v)

    types = {}
    for k,vals in all_values.iteritems():
        try:
            _ = [ int(a) for a in vals ]
            types[k] = int
        except:
            try:
                _ = [ float(a) for a in vals ]
                types[k] = float
            except:
                types[k] = None
    
    groups = defaultdict(list)
    for i,a in enumerate(annotations):
        groups[tuple(a[k] for k in separate)].append(i)

    different_in_all = set(k \
        for k,vals in all_values.iteritems() \
        if len(vals) == len(annotations) or len(vals) == 1)

    other_relevant = set(all_values.keys()) - different_in_all - ignore - set(separate)
    if consider != None:
        other_relevant &= set(consider)
    other_relevant = sorted(other_relevant) #TODO how to order them?

    def relevant_vals(annotation):
        if isinstance(annotation, tuple):
            return annotation
        return tuple(annotation[v] if types[v] == None else types[v](annotation[v]) 
            for v in other_relevant)

    other_relevant_d = defaultdict(list)
    for i,a in enumerate(annotations):
        other_relevant_d[relevant_vals(a)].append(i)

    if add_empty: #fill in with "empty" relevant vals
        ngroups = {}
        for g in groups:
            ngroups[g] = groups[g] + list(set(other_relevant_d) - 
                set([ relevant_vals(annotations[e]) for e in groups[g] ]))
        groups = ngroups

    ngroups = {}
    for g in groups:
        elements = list(groups[g])
        ngroups[g] = map(lambda x: x if isinstance(x,int) else None,
            sorted(elements, key=lambda x: relevant_vals(annotations[x] if isinstance(x,int) else x)))
        
    return ngroups

class MyHeaderView(QHeaderView):
    def __init__(self, *args):
        QHeaderView.__init__(self, *args)
        
    def mouseMoveEvent(self, event):
        event.ignore()
        
    def wheelEvent(self, event):
        event.ignore()
        
class KeyValueContextHandler(ContextHandler):
    def match(self, context, imperfect, items):
        items = set(items)
        saved_items = set(getattr(context, "items", []))
        print "Saved Context", saved_items  
        if imperfect:
            return len(items.intersection(saved_items))/len(items.union(saved_items))
        else:
            return items == saved_items
        
    def findOrCreateContext(self, widget, items):        
        index, context, score = self.findMatch(widget, self.findImperfect, items)
        if context:
            if index < 0:
                self.addContext(widget, context)
            else:
                self.moveContextUp(widget, index)
            return context, False
        else:
            context = self.newContext()
            context.items = items
            self.addContext(widget, context)
            return context, True
        
class OWGenotypeDistances(OWWidget):
    contextHandlers = {"": KeyValueContextHandler("")}
    settingsList = []
    def __init__(self, parent=None, signalManager=None, title="Genotype Distances"):
        OWWidget.__init__(self, parent, signalManager, title)
        
        self.inputs = [("Example Table", ExampleTable, self.set_data)]
        self.outputs = [("Distances", Orange.core.SymMatrix)]
        
        self.loadSettings()
        
        ########
        # GUI
        ########
        
        self.info_box = OWGUI.widgetLabel(OWGUI.widgetBox(self.controlArea, "Info",
                                                         addSpace=True),
                                         "No data on input")
        
        box = OWGUI.widgetBox(self.controlArea, "Separate By",
                              addSpace=True)
        
        self.separate_view = QListView()
        self.separate_view.setSelectionMode(QListView.MultiSelection)
        box.layout().addWidget(self.separate_view)
        
        box = OWGUI.widgetBox(self.controlArea, "Relevant attributes",
                              addSpace=True)
        
        self.relevant_view = QListView()
        self.relevant_view.setSelectionMode (QListView.MultiSelection)
        box.layout().addWidget(self.relevant_view)
        
        self.distance_view = OWGUI.comboBox(self.controlArea, self, "distance_measure",
                                            box="Distance Measure")
        self.groups_box = OWGUI.widgetBox(self.mainArea, "Groups")
        self.groups_scroll_area = QScrollArea()
        self.groups_box.layout().addWidget(self.groups_scroll_area)
        
        self.data = None
        self._disable_updates = False
        
        self.resize(800, 600)
        
    def clear(self):
        pass
        
    def set_data(self, data=None):
        """ Set the input example table.
        """
        self.closeContext()
        self.clear()
        self.data = data
        if data:
            self.update_control()
            self.split_data()
            
    def update_control(self):
        """ Update the control area of the widget. Populate the list
        views with keys from attribute labels.
        """
        attrs = [attr.attributes.items() for attr in data.domain.attributes]
        attrs = reduce(set.union, attrs, set())
        values = defaultdict(set)
        for key, value in attrs:
            values[key].add(value)
        keys = [key for key in values if len(values[key]) > 1]
         
        model = PyListModel(keys)
        self.separate_view.setModel(model)
        self.connect(self.separate_view.selectionModel(),
                     SIGNAL("selectionChanged(QItemSelection, QItemSelection)"),
                     self.on_separate_key_changed)
        
        model = PyListModel(keys)
        self.relevant_view.setModel(model)
        self.connect(self.relevant_view.selectionModel(),
                     SIGNAL("selectionChanged(QItemSelection, QItemSelection)"),
                     self.on_relevant_key_changed)
        
        self.openContext("", attrs)
        
        # Get the selected keys from the open context
        context = self.currentContexts[""]
        separate_keys = getattr(context, "separate_keys", set())
        relevant_keys = getattr(context, "relevant_keys", set())
        
        def select(model, selection_model, selected_items):
            all_items = list(model)
            indices = [all_items.index(item) for item in selected_items]
            for ind in indices:
                selection_model.select(model.index(ind), QItemSelectionModel.Select)
                
        self._disable_updates = True
        try:
            select(self.separate_view.model(),
                   self.separate_view.selectionModel(),
                   separate_keys)
            
            select(self.relevant_view.model(),
                   self.relevant_view.selectionModel(),
                   relevant_keys)
        finally:
            self._disable_updates = False
        
    def on_separate_key_changed(self, *args):
        if not self._disable_updates:
            context = self.currentContexts[""]
            context.separate_keys = self.selected_separeate_by_keys()
            self.split_data()
    
    def on_relevant_key_changed(self, *args):
        if not self._disable_updates:
            context = self.currentContexts[""]
            context.relevant_keys = self.selected_relevant_keys()
            self.split_data()
        
    def selected_separeate_by_keys(self):
        """ Return the currently selected separate by keys
        """
        rows = self.separate_view.selectionModel().selectedRows()
        rows = sorted([idx.row() for idx in rows])
        keys = [self.separate_view.model()[row] for row in rows]
        return keys
        
    def selected_relevant_keys(self):
        """ Return the currently selected relevant keys
        """
        rows = self.relevant_view.selectionModel().selectedRows()
        rows = sorted([idx.row() for idx in rows])
        keys = [self.relevant_view.model()[row] for row in rows]
        return keys
    
    def split_data(self):
        """ Split the data and update the Groups widget
        """
        separate_keys = self.selected_separeate_by_keys()
        relevant_keys = self.selected_relevant_keys()
        
        if not separate_keys:
            return
        ann = separate_by(self.data, separate_keys, consider=relevant_keys)
        print ann
        
        split_data = []
        
        # Collect relevant key value pairs for all columns
        relevant_items = {}
        for keys, indices in sorted(ann.items()):
            for i, ind in enumerate(indices):
                if ind is not None:
                    attr = self.data.domain[ind]
                    relevant_items[i] = [(key, attr.attributes[key]) \
                                         for key in relevant_keys]
                    
        def get_attr(attr_index, i):
            if attr_index is None:
                attr = Orange.data.variable.Continuous("missing")
                attr.attributes.update(relevant_items[i])
                return attr
            else:
                return self.data.domain[attr_index]
            
        for keys, indices in sorted(ann.items()):
            attrs = [get_attr(attr_index, i) for i, attr_index in enumerate(indices)]
            domain = Orange.data.Domain(attrs, None)
            newdata = Orange.data.Table(domain, self.data)
            split_data.append((keys, newdata))
            
        self.set_groups(separate_keys, split_data, relevant_keys)
        
    def set_groups(self, keys, groups, relevant_keys):
        """ Set the current data groups and update the Group widget
        """
        layout = QVBoxLayout()
        header_widths = []
        header_views = []
        palette = self.palette()
        for ann_vals, table in groups:
            label = QLabel(" <b>|</b> ".join(["<b>{0}</b> = {1}".format(key,val) \
                                     for key, val in zip(keys, ann_vals)]))
            
            model = QStandardItemModel()
            for i, attr in enumerate(table.domain.attributes):
                item = QStandardItem()
                if attr.name != "missing":
                    header_text = ["{0}={1}".format(key, attr.attributes[key]) \
                                   for key in relevant_keys]
                    header_text = "\n".join(header_text)
                    item.setData(QVariant(header_text), Qt.DisplayRole)
                    item.setData(QVariant(attr.name), Qt.ToolTipRole)
                    
                else:
#                    header_text = "\n".join("{0}=?".format(key) for key in relevant_keys)
                    header_text = ["{0}={1}".format(key, attr.attributes[key]) \
                                   for key in relevant_keys]
                    header_text = "\n".join(header_text)
                    item.setData(QVariant(header_text), Qt.DisplayRole)
                    item.setFlags(Qt.NoItemFlags)
                    
#                    item.setData(QVariant(palette.color(QPalette.Disabled, QPalette.Text)), Qt.ForegroundRole)
                    item.setData(QVariant(QColor(Qt.red)), Qt.ForegroundRole)
#                    item.setData(QVariant(QColor(Qt.red)), Qt.BackgroundRole)
                    item.setData(QVariant(palette.color(QPalette.Disabled, QPalette.Window)), Qt.BackgroundRole)
                    item.setData(QVariant("Missing feature."), Qt.ToolTipRole)
                
                model.setHorizontalHeaderItem(i, item)
            attr_count = len(table.domain.attributes)
            view = MyHeaderView(Qt.Horizontal)
            view.setResizeMode(QHeaderView.Fixed)
            view.setModel(model)
            hint = view.sizeHint()
            view.setMaximumHeight(hint.height())
            
            widths = [view.sectionSizeHint(i) for i in range(attr_count)]
            header_widths.append(widths)
            header_views.append(view)
            
            layout.addWidget(label)
            layout.addWidget(view)
            layout.addSpacing(8)
            
        # Make all header sections the same width
        width_sum = 0
        max_header_count = max([h.count() for h in header_views])
        for i in range(max_header_count):
            max_width = max([w[i] for w in header_widths if i < len(w)] or [0])
            for view in header_views:
                if i < view.count():
                    view.resizeSection(i, max_width)
            width_sum += max_width + 2
                
        for h in header_views:
            h.setMinimumWidth(h.length() + 4)
            
        widget = QWidget()
        widget.setLayout(layout)
        widget.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Maximum)
        layout.activate()
        
        max_width = max(h.length() for h in header_views) + 20
        
        left, top, right, bottom  = self.getContentsMargins()
        widget.setMinimumWidth(width_sum)
        widget.setMinimumWidth(max_width + left + right)
        self.groups_scroll_area.setWidget(widget)
        
        #Compute distances here
        
        
if __name__ == "__main__":
    import os, sys
    app = QApplication(sys.argv )
    w = OWGenotypeDistances()
#    data = Orange.data.Table(os.path.expanduser("~/Documents/dicty-express-sample.tab"))
    data = Orange.data.Table(os.path.expanduser("~/Downloads/tmp.tab"))
    w.set_data(data)
    w.show()
    app.exec_()
    w.saveSettings()
    
