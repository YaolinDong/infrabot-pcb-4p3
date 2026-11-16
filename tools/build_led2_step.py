# SPDX-License-Identifier: MIT
# Copyright (c) 2026 YaolinDong
"""Optional STEP model builder for the R6 formed-lead LED2 assembly.

Requires cadquery-ocp (Open CASCADE Python bindings); the STEP is checked in
alongside the native project footprint. Coordinates are millimetres.
"""
from pathlib import Path
from OCP.gp import gp_Pnt, gp_Dir, gp_Ax2
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakeSphere, BRepPrimAPI_MakeBox
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakePolygon
from OCP.BRepOffsetAPI import BRepOffsetAPI_ThruSections
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Common, BRepAlgoAPI_Fuse
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.STEPControl import STEPControl_Writer, STEPControl_AsIs
from OCP.Interface import Interface_Static

base = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0,0,4),gp_Dir(0,0,1)),2.9,1).Shape()
cut = BRepPrimAPI_MakeBox(gp_Pnt(2.6,-4,3),4,8,3).Shape()
base = BRepAlgoAPI_Cut(base,cut).Shape()
barrel = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0,0,5),gp_Dir(0,0,1)),2.5,4.2).Shape()
sphere = BRepPrimAPI_MakeSphere(gp_Pnt(0,0,9.2),2.5).Shape()
upper = BRepPrimAPI_MakeBox(gp_Pnt(-3,-3,9.2),6,6,3).Shape()
dome = BRepAlgoAPI_Common(sphere,upper).Shape()
shape = BRepAlgoAPI_Fuse(BRepAlgoAPI_Fuse(base,barrel).Shape(),dome).Shape()
pins = [('1',1.905,-.9,-2.6),('2',.635,.9,-3.4),('3',-.635,-.9,-3.0),('4',-1.905,.9,-2.2)]
for _,x,y,tip in pins:
    loft = BRepOffsetAPI_ThruSections(True,True,1e-6)
    for cx,cy,z in [(x,y,tip),(x,y,1.1),(x,0,2),(x,0,4.1)]:
        wire=BRepBuilderAPI_MakePolygon()
        for dx,dy in [(-.25,-.25),(.25,-.25),(.25,.25),(-.25,.25)]:wire.Add(gp_Pnt(cx+dx,cy+dy,z))
        wire.Close();loft.AddWire(wire.Wire())
    loft.Build();assert loft.IsDone()
    shape=BRepAlgoAPI_Fuse(shape,loft.Shape()).Shape()
assert BRepCheck_Analyzer(shape).IsValid()
Interface_Static.SetCVal_s('write.step.unit','MM')
writer=STEPControl_Writer();writer.Transfer(shape,STEPControl_AsIs)
dest=Path(__file__).resolve().parents[1]/'hardware/library/LED2_R6_formed.step';status=writer.Write(str(dest))
print(status,dest)
