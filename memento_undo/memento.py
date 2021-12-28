__author__ = 'jrootham'

import tkinter as tk
import math

NODE_WIDTH = 40
NODE_HEIGHT = 40
TEXT_OFFSET_X = 10
TEXT_OFFSET_Y = 10
SEPARATION = 1

def create_db(cursor):

    undo_redo = "CREATE TABLE undo_redo ("
    undo_redo += "id INTEGER PRIMARY KEY,"
    undo_redo += "parent INTEGER,"
    undo_redo += "sibling INTEGER,"
    undo_redo += "child INTEGER,"
    undo_redo += "type INTEGER,"
    undo_redo += "data INTEGER"
    undo_redo += ");"

    cursor.execute(undo_redo)

    state = "CREATE TABLE state ("
    state += "id INTEGER PRIMARY KEY,"
    state += "root INTEGER,"
    state += "current INTEGER,"
    state += "current_id INTEGER"
    state += ");"

    cursor.execute(state)

class MementoBase:
    def __init__(self):
        self.root = None
        self.current = None
        self.tree_memento = None

    def set_current(self, thing):
        self.current = thing
        if not self.tree_memento is None:
            self.tree_memento.current = thing

    def undo(self, model):
        self.current.undo(model)
        if not self.current.parent is None:
            self.current = self.current.parent

            if not self.tree_memento is None:
                self.tree_memento.current = self.current

    def redo(self, model, ask):
        if not self.current.child is None:
            if not self.current.child.sibling is None:
                self.current = ask(self.current.child)
            else:
                self.current = self.current.child

            self.current.redo(model)

            if not self.tree_memento is None:
                self.tree_memento.current = self.current

    def goto(self, model, target):

        stack = []

        thing = target

        while not thing.parent is None:
            if not thing.parent.child.sibling is None:
                stack.append(thing)
            thing = thing.parent

        def ask(possible):
            return stack.pop()

        self.root.redo(model)
        self.current = self.root

        while self.current != target:
            self.redo(model, ask)


class Memento(MementoBase):

    def __init__(self, cursor, make_thing):
        MementoBase.__init__(self)

        self.tree = None

        self.max_depth = 0
        self.cursor = cursor

        state_list = cursor.execute("SELECT root, current, current_id FROM state WHERE id=1;")
        state_row = state_list.fetchone()

        root_id = state_row[0]
        current_id = state_row[1]
        current_id_value = state_row[2]

        self.id_source = Id(current_id_value)
        self.fill(cursor, make_thing, root_id, current_id)

    def fill(self, cursor, make_thing, root_id, current_id):
        thing_dict = {}
        link_dict = {}

        undo_redo = "SELECT id, type, data, parent, child,  sibling "
        undo_redo += "FROM undo_redo ORDER BY id;"
        for row in cursor.execute(undo_redo).fetchall():
            id = row[0]
            link = {"child":row[4], "sibling":row[5]}
            link_dict[id] = link
            if row[3] != 0:
                parent = thing_dict[row[3]]
            else:
                parent = None

            thing_dict[id] = make_thing[row[1]](cursor, row[0], parent, row[2])

        for id, thing in thing_dict.viewitems():
            self.max_depth = max(self.max_depth, thing.depth)

            child_id = link_dict[id]["child"]
            if child_id != 0:
                thing.child = thing_dict[child_id]

            sibling_id = link_dict[id]["sibling"]
            if sibling_id != 0:
                thing.sibling = thing_dict[sibling_id]

        self.root = thing_dict[root_id]
        self.current = thing_dict[current_id]

    def save(self, cursor):
        update = "UPDATE state SET root=?,current=?,current_id=?;"
        cursor.execute(update, (self.root.id, self.current.id, self.id_source.id))

    def next(self):
        return self.id_source.next()

    def connect(self, thing):
        self.max_depth = max(self.max_depth, thing.depth)

        thing.save(self.cursor)

        self.set_current(thing)

        if not thing.parent is None:
            if thing.parent.child is None:
                thing.parent.update_child(self.cursor, thing)
            else:
                sibling = thing.parent.child
                while not sibling.sibling is None:
                    sibling = sibling.sibling

                sibling.update_sibling(self.cursor, thing)

        self.draw_all()

    def open_tree(self, canvas):
        self.tree = canvas
        self.tree_memento = MememtoDerived(self)
        self.draw_all()

    def close_tree(self):
        self.tree_memento = None
        self.tree = None

    def draw_all(self):
        if not self.tree is None:
            self.tree.delete(Tk.ALL)
            tree_id = self.tree_memento.current.id
            size = (self.node_width(), self.node_height())
            draw_tree(self.tree, (0,0), 0, size, self.root, self.current.id, tree_id)

    def node_height(self):
        height = self.tree.winfo_height()
        return min(NODE_HEIGHT, (float(height) / (self.max_depth + 1)) - SEPARATION)

    def node_width(self):
        width = self.tree.winfo_width()
        return min(NODE_WIDTH, (float(width) / self.max_column()) - SEPARATION)

    def max_column(self):
        return max_column(self.root, 1)

class MememtoDerived(MementoBase):
    def __init__(self, other):
        MementoBase.__init__(self)
        self.root = other.root
        self.current = other.current


class Id:
    def __init__(self, id):
        self.id = id

    def next(self):
        self.id += 1
        return self.id


class UndoRedo:
    def __init__(self, id, parent):
        self.id = id
        self.parent = parent
        self.sibling = None
        self.child = None

        if not parent is None:
            self.depth = parent.depth + 1
        else:
            self.depth = 0

    def name(self):
        return ''

    def colour(self):
        return ''

    def ask_text(self):
        return self.name() + " " + self.ask_option()

    def ask_option(self):
        return ''

    def undo(self, model):
        pass

    def redo(self, model):
        pass

    def save(self, cursor):
        sql = "INSERT INTO undo_redo (id,parent,child,sibling) VALUES(?,?,0,0)"
        cursor.execute(sql, (self.id, self.parent.id))

    def update_child(self, cursor, child):
        self.child = child
        cursor.execute("UPDATE undo_redo SET child=? WHERE id=?;", (child.id, self.id))

    def update_sibling(self, cursor, sibling):
        self.sibling = sibling
        cursor.execute("UPDATE undo_redo SET sibling=? WHERE id=?;", (sibling.id, self.id))

# Local draw functions

#function drawTree(context, displacement, offset, itemHeight, separation, tree) {
# var columns = 1;
#
#  if (tree.down != null){
#    columns = drawTree(context, displacement, offset, itemHeight, separation, tree.down);
#  }
#
#  if (tree.across != null) {
#    context.fillStyle="#606060";
#    context.fillRect(offset + TREE_WIDTH - displacement.x,
#      (tree.depth * (itemHeight + separation)) - displacement.y,
#      columns * TREE_WIDTH, 1);
#
#    var delta = offset + (TREE_WIDTH + separation) * columns;
#    columns += drawTree(context, displacement, delta, itemHeight, separation, tree.across);
#  }
#
#  return columns;
#}


def draw_tree(canvas, displacement, offset, item_size, tree, current_id, tree_id):
    (item_width, item_height) = item_size
    columns = 1

    draw_node(canvas, displacement, offset, item_size, tree, current_id, tree_id)
    if not tree.child is None:
        columns = draw_tree(canvas, displacement, offset, item_size, tree.child, current_id, tree_id)

    if not tree.sibling is None:
        draw_connection(canvas, offset, displacement, item_size, tree, columns)
        delta = offset + (item_width + SEPARATION) * columns
        columns += draw_tree(canvas, displacement, delta, item_size, tree.sibling, current_id, tree_id)

    return columns

#  context.fillStyle=tree.colour;
#  var x = offset - displacement.x;
#  var y = (tree.depth * (itemHeight + separation)) - displacement.y;
#  context.fillRect(x, y, TREE_WIDTH, itemHeight);
#
#  if (itemHeight == SMALLEST) {
#    context.font="20px Arial";
#    context.fillStyle = tree.textColour;
#    context.fillText(tree.text, x + 3, y + 25);
#  }


def draw_node(canvas, displacement, offset, item_size, tree, current_id, tree_id):
    (item_width, item_height) = item_size
    (dx, dy) = displacement
    x = offset - dx
    y = (tree.depth * (item_height + SEPARATION)) - dy

    colour = tree.colour()
    if tree.id == current_id or tree.id == tree_id:
        colour = "black"

    canvas.create_rectangle(x, y, x + item_width, y + item_height, width=0, fill=colour)

    if item_height == NODE_HEIGHT and item_width == NODE_WIDTH:
        tx = x + TEXT_OFFSET_X
        ty = y + TEXT_OFFSET_Y
        canvas.create_text((tx, ty), text=tree.name(), fill="white", anchor=Tk.NW, font=("System", 14))

def draw_connection(canvas, offset, displacement, item_size, tree, columns):
    (item_width, item_height) = item_size
    (dx, dy) = displacement
    x = offset + item_width - dx
    y = (tree.depth * (item_height + SEPARATION)) - dy

    canvas.create_line(x, y, x + columns * item_width, y)

def max_column(tree, column):
    stack = []

    while not tree.child is None:
        if not tree.sibling is None:
            stack.append(tree.sibling)

        tree = tree.child

    column += 1

    while len(stack) > 0:
        column = max_column(stack.pop(), column)

    return column
