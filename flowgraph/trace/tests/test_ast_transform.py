# Copyright 2018 IBM Corp.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import absolute_import

import ast
from textwrap import dedent
import unittest

from astor import to_source

from ..ast_transform import *
from ..ast_util import gensym


class TestASTTransform(unittest.TestCase):
    """ Test cases for abstract syntax tree (AST) transformers.
    """

    def test_single_assign(self):
        """ Are single assignments are preserved exactly?
        """
        node = ast.parse('x = f()')
        EliminateMultipleTargets().visit(node)
        self.assertEqual(to_source(node).strip(), 'x = f()')

        node = ast.parse('x, y = f()')
        EliminateMultipleTargets().visit(node)
        self.assertEqual(to_source(node).strip(), 'x, y = f()')
    
    def test_compound_assign_with_tuple(self):
        """ Can we simplify compound assignments with tuple literal values?
        """
        node = ast.parse('x, y = f(), g()')
        gensym.reset()
        EliminateMultipleTargets().visit(node)
        self.assertEqual(to_source(node), dedent("""\
            __gensym_1 = f()
            __gensym_2 = g()
            x = __gensym_1
            y = __gensym_2
        """))

    def test_multiple_assign_simple(self):
        """ Can we eliminate a simple multiple assignment?
        """
        node = ast.parse('x = y = f()')
        gensym.reset()
        EliminateMultipleTargets().visit(node)
        self.assertEqual(to_source(node), dedent("""\
            __gensym_1 = f()
            x = __gensym_1
            y = __gensym_1
        """))
    
    def test_multiple_assign_compound(self):
        """ Can we eliminate a compound multiple assignment?
        """
        node = ast.parse('a, b = x, y = f()')
        gensym.reset()
        EliminateMultipleTargets().visit(node)
        self.assertEqual(to_source(node), dedent("""\
            __gensym_1, __gensym_2 = f()
            x = __gensym_1
            y = __gensym_2
            a = __gensym_1
            b = __gensym_2
        """))
    
    def test_multiple_assign_simple_and_compound(self):
        """ Can we eliminate a multiple assignment involing both simple and
        compound targets?
        """
        node = ast.parse('z = x, y = f()')
        gensym.reset()
        EliminateMultipleTargets().visit(node)
        self.assertEqual(to_source(node), dedent("""\
            __gensym_1, __gensym_2 = f()
            x = __gensym_1
            y = __gensym_2
            z = __gensym_1, __gensym_2
        """))
    
    def test_simple_getattr(self):
        """ Can we replace a simple attribute access with `getattr`?
        """
        node = ast.parse(dedent("""
            x = obj.x
            y = obj.y
        """))
        AttributesToFunctions().visit(node)
        self.assertEqual(to_source(node), dedent("""\
            x = getattr(obj, 'x')
            y = getattr(obj, 'y')
        """))
    
    def test_compound_getattr(self):
        """ Can we replace a compound attribute access with `getattr`s?
        """
        node = ast.parse('x = container.obj.x')
        AttributesToFunctions().visit(node)
        self.assertEqual(to_source(node), dedent("""\
            x = getattr(getattr(container, 'obj'), 'x')
        """))
    
    def test_simple_setattr(self):
        """ Can we replace a simple attribute assignment with `setattr`?
        """
        node = ast.parse(dedent("""
            foo.x = 10
            foo.y = 100
        """))
        AttributesToFunctions().visit(node)
        self.assertEqual(to_source(node), dedent("""\
            setattr(foo, 'x', 10)
            setattr(foo, 'y', 100)
        """))
    
    def test_compound_setattr(self):
        """ Can we replace a compound attribute asssignment with `getattr` and
        `setattr`?
        """
        node = ast.parse('container.foo.x = 10')
        AttributesToFunctions().visit(node)
        self.assertEqual(to_source(node), dedent("""\
            setattr(getattr(container, 'foo'), 'x', 10)
        """))
    
    def test_delattr(self):
        """ Can we replace an attribute deletion with `delattr`?
        """
        node = ast.parse('del foo.x')
        AttributesToFunctions().visit(node)
        self.assertEqual(to_source(node), dedent("""\
            delattr(foo, 'x')
        """))
    
    def test_unary_op(self):
        """ Can we replace unary operators with function calls?
        """
        node = ast.parse('-x')
        OperatorsToFunctions().visit(node)
        self.assertEqual(to_source(node).strip(), 'operator.neg(x)')

        node = ast.parse('~x')
        OperatorsToFunctions().visit(node)
        self.assertEqual(to_source(node).strip(), 'operator.invert(x)')
    
    def test_unary_negate_literal(self):
        """ Check that negations of literals aren't transformed.
        """
        node = ast.parse('-1')
        OperatorsToFunctions().visit(node)
        self.assertEqual(to_source(node).strip(), '-1')
    
    def test_binary_op(self):
        """ Can we replace binary operators with function calls?
        """
        node = ast.parse('x+y')
        OperatorsToFunctions().visit(node)
        self.assertEqual(to_source(node).strip(), 'operator.add(x, y)')

        node = ast.parse('x*y')
        OperatorsToFunctions().visit(node)
        self.assertEqual(to_source(node).strip(), 'operator.mul(x, y)')
    
    def test_inplace_binary_op(self):
        """ Can we replace an inplace binary operation with an assignment?
        """
        node = ast.parse('x += 1')
        InplaceOperatorsToFunctions().visit(node)
        self.assertEqual(to_source(node).strip(), 'x = operator.iadd(x, 1)')

        node = ast.parse('x *= y')
        InplaceOperatorsToFunctions().visit(node)
        self.assertEqual(to_source(node).strip(), 'x = operator.imul(x, y)')
    
    def test_comparison_op(self):
        """ Can we replace comparison operators with function calls?
        """
        node = ast.parse('x < y')
        OperatorsToFunctions().visit(node)
        self.assertEqual(to_source(node).strip(), 'operator.lt(x, y)')

        node = ast.parse('x <= y')
        OperatorsToFunctions().visit(node)
        self.assertEqual(to_source(node).strip(), 'operator.le(x, y)')
    
    def test_contains_op(self):
        """ Can we replace containment operators with function calls?
        """
        node = ast.parse('b in a')
        OperatorsToFunctions().visit(node)
        self.assertEqual(to_source(node).strip(), 'operator.contains(a, b)')

        node = ast.parse('b not in a')
        OperatorsToFunctions().visit(node)
        self.assertEqual(to_source(node).strip(),
                         'operator.not_(operator.contains(a, b))')
        
    def test_simple_getitem(self):
        """ Can we replace a simple indexing operation with `getitem`?
        """
        node = ast.parse('x[0]')
        IndexingToFunctions().visit(node)
        self.assertEqual(to_source(node).strip(), 'operator.getitem(x, 0)')
    
    def test_slice_getitem(self):
        """ Can we replace a slice indexing operation with `getitem`?
        """
        node = ast.parse('x[0:1]')
        IndexingToFunctions().visit(node)
        self.assertEqual(to_source(node).strip(),
                         'operator.getitem(x, slice(0, 1))')
        
        node = ast.parse('x[::2]')
        IndexingToFunctions().visit(node)
        self.assertEqual(to_source(node).strip(),
                         'operator.getitem(x, slice(None, None, 2))')
    
    def test_multidim_slice_getitem(self):
        """ Can we replace a multidimensional slice with `getitem`?
        """
        node = ast.parse('x[:m, :n]')
        IndexingToFunctions().visit(node)
        self.assertEqual(to_source(node).strip(),
                         'operator.getitem(x, (slice(m), slice(n)))')
    
    def test_simple_setitem(self):
        """ Can we replace an indexed assignment with `setitem`?
        """
        node = ast.parse('x[0] = 1')
        IndexingToFunctions().visit(node)
        self.assertEqual(to_source(node).strip(), 'operator.setitem(x, 0, 1)')
    
    def test_simple_delitem(self):
        """ Can we replace an indexed deletion with `delitem`?
        """
        node = ast.parse('del x[0]')
        IndexingToFunctions().visit(node)
        self.assertEqual(to_source(node).strip(), 'operator.delitem(x, 0)')
    
    def test_inplace_setitem(self):
        """ Can we replace an inplace indexed binary op with function calls?
        """
        node = ast.parse('x[n] += 1')
        IndexingToFunctions('op').visit(node)
        self.assertEqual(to_source(node), dedent("""\
            op.setitem(x, n, op.iadd(op.getitem(x, n), 1))
        """))
    
    def test_inplace_setitem_gensym_target(self):
        """ Is the target value gensym-ed in inplace indexed operations?
        """
        node = ast.parse('x.data[n] += 1')
        gensym.reset()
        IndexingToFunctions('op').visit(node)
        self.assertEqual(to_source(node), dedent("""\
            __gensym_1 = x.data
            op.setitem(__gensym_1, n, op.iadd(op.getitem(__gensym_1, n), 1))
        """))
    
    def test_inplace_setitem_gensym_index(self):
        """ Is the index value gensym-ed in inplace indexed operations?
        """
        node = ast.parse('x[m:m+n] += 1')
        gensym.reset()
        IndexingToFunctions('op').visit(node)
        self.assertEqual(to_source(node), dedent("""\
            __gensym_1 = slice(m, m + n)
            op.setitem(x, __gensym_1, op.iadd(op.getitem(x, __gensym_1), 1))
        """))
    
    def test_inplace_setitem_gensym_both(self):
        """ Are both target and index values gensym-ed in inplace indexed ops?
        """
        node = ast.parse('x.data[m:m+n] += 1')
        gensym.reset()
        IndexingToFunctions('op').visit(node)
        self.assertEqual(to_source(node), dedent("""\
            __gensym_1 = x.data
            __gensym_2 = slice(m, m + n)
            op.setitem(__gensym_1, __gensym_2, op.iadd(op.getitem(__gensym_1,
                __gensym_2), 1))
        """))
    
    def test_list_literal(self):
        """ Can we replace a list literal with a function call?
        """
        node = ast.parse('[1,2,3]')
        ContainerLiteralsToFunctions().visit(node)
        result = 'operator.__list__(1, 2, 3)'
        self.assertEqual(to_source(node).strip(), result)
    
    def test_tuple_literal(self):
        """ Can we replace a tuple literal with a function call?
        """
        node = ast.parse('(1,2,3)')
        ContainerLiteralsToFunctions().visit(node)
        result = 'operator.__tuple__(1, 2, 3)'
        self.assertEqual(to_source(node).strip(), result)
    
    def test_set_literal(self):
        """ Can we replace a set literal with a function call?
        """
        node = ast.parse('{1,2,3}')
        ContainerLiteralsToFunctions().visit(node)
        result = 'operator.__set__(1, 2, 3)'
        self.assertEqual(to_source(node).strip(), result)
    
    def test_dict_literal(self):
        """ Can we replace a dictionary literal whose keys are strings with a
        function call?
        """
        node = ast.parse("{'x': 1, 'y': 2}")
        ContainerLiteralsToFunctions().visit(node)
        result = 'dict(x=1, y=2)'
        self.assertEqual(to_source(node).strip(), result)
    
    def test_compound_sequence_literal(self):
        """ Can we replace a compound sequence literal with function calls?
        """
        node = ast.parse("[ ('x',0), ('y',1) ]")
        ContainerLiteralsToFunctions('op').visit(node)
        result = "op.__list__(op.__tuple__('x', 0), op.__tuple__('y', 1))"
        self.assertEqual(to_source(node).strip(), result)


if __name__ == '__main__':
    unittest.main()
