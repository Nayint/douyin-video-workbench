import AppKit
let root = CommandLine.arguments[1]
for size in [16, 32, 64, 128, 256, 512, 1024] {
 let bitmap = NSBitmapImageRep(bitmapDataPlanes:nil, pixelsWide:size, pixelsHigh:size, bitsPerSample:8, samplesPerPixel:4, hasAlpha:true, isPlanar:false, colorSpaceName:.deviceRGB, bytesPerRow:0, bitsPerPixel:0)!
 NSGraphicsContext.saveGraphicsState()
 NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep:bitmap)
 let ctx = NSGraphicsContext.current!.cgContext
 ctx.scaleBy(x:CGFloat(size)/1024,y:CGFloat(size)/1024)
 let bg = NSBezierPath(roundedRect:NSRect(x:30,y:30,width:964,height:964),xRadius:218,yRadius:218)
 NSGradient(starting:NSColor(calibratedRed:0.34,green:0.49,blue:0.32,alpha:1),ending:NSColor(calibratedRed:0.11,green:0.23,blue:0.17,alpha:1))!.draw(in:bg,angle:-70)
 let rim=NSBezierPath(roundedRect:NSRect(x:52,y:52,width:920,height:920),xRadius:200,yRadius:200)
 NSColor.white.withAlphaComponent(0.13).setStroke();rim.lineWidth=3;rim.stroke()
 let flask=NSBezierPath()
 flask.move(to:NSPoint(x:421,y:771));flask.line(to:NSPoint(x:603,y:771))
 flask.line(to:NSPoint(x:603,y:723));flask.line(to:NSPoint(x:580,y:723));flask.line(to:NSPoint(x:580,y:582))
 flask.curve(to:NSPoint(x:713,y:335),controlPoint1:NSPoint(x:580,y:550),controlPoint2:NSPoint(x:713,y:380))
 flask.curve(to:NSPoint(x:663,y:258),controlPoint1:NSPoint(x:738,y:289),controlPoint2:NSPoint(x:709,y:258))
 flask.line(to:NSPoint(x:361,y:258));flask.curve(to:NSPoint(x:311,y:335),controlPoint1:NSPoint(x:315,y:258),controlPoint2:NSPoint(x:286,y:289))
 flask.curve(to:NSPoint(x:444,y:582),controlPoint1:NSPoint(x:311,y:380),controlPoint2:NSPoint(x:444,y:550))
 flask.line(to:NSPoint(x:444,y:723));flask.line(to:NSPoint(x:421,y:723));flask.close()
 NSColor(calibratedRed:0.90,green:0.96,blue:0.78,alpha:1).setStroke();flask.lineWidth=30;flask.lineJoinStyle = .round;flask.stroke()
 let liquid=NSBezierPath();liquid.move(to:NSPoint(x:381,y:419));liquid.curve(to:NSPoint(x:643,y:419),controlPoint1:NSPoint(x:461,y:464),controlPoint2:NSPoint(x:566,y:376));liquid.line(to:NSPoint(x:680,y:335));liquid.curve(to:NSPoint(x:659,y:294),controlPoint1:NSPoint(x:692,y:308),controlPoint2:NSPoint(x:676,y:294));liquid.line(to:NSPoint(x:365,y:294));liquid.curve(to:NSPoint(x:344,y:335),controlPoint1:NSPoint(x:348,y:294),controlPoint2:NSPoint(x:332,y:308));liquid.close()
 NSColor(calibratedRed:0.69,green:0.83,blue:0.49,alpha:1).setFill();liquid.fill()
 NSColor(calibratedRed:0.90,green:0.96,blue:0.78,alpha:1).setFill()
 for (x,y,r) in [(503.0,492.0,17.0),(545.0,548.0,12.0),(484.0,602.0,10.0)] {NSBezierPath(ovalIn:NSRect(x:x-r,y:y-r,width:2*r,height:2*r)).fill()}
 NSGraphicsContext.restoreGraphicsState()
 let bytes=bitmap.representation(using:.png,properties:[:])!
 for (base,scale) in [(16,1),(16,2),(32,1),(32,2),(128,1),(128,2),(256,1),(256,2),(512,1),(512,2)] where base*scale==size {
  let name="icon_\(base)x\(base)"+(scale==2 ? "@2x" : "")+".png"
  try bytes.write(to:URL(fileURLWithPath:root).appendingPathComponent(name))
 }
}
