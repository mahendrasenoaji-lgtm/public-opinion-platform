import PDFKit
import AppKit
let a = CommandLine.arguments
let doc = PDFDocument(url: URL(fileURLWithPath: a[1]))!
for i in 0..<doc.pageCount {
  let p = doc.page(at: i)!
  let r = p.bounds(for: .mediaBox)
  let img = p.thumbnail(of: NSSize(width: r.width*1.4, height: r.height*1.4), for: .mediaBox)
  let rep = NSBitmapImageRep(data: img.tiffRepresentation!)!
  try! rep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: "\(a[2])/s\(String(format: "%02d", i+1)).png"))
}
print(doc.pageCount)
