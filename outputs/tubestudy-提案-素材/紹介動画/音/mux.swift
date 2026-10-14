// 動画（MP4）に音（M4A）を重ねる。映像はそのまま（再エンコードしない）。 mux <video.mp4> <audio.m4a> <out.mp4>
import Foundation
import AVFoundation
let a = CommandLine.arguments
let video = AVURLAsset(url: URL(fileURLWithPath: a[1]))
let audio = AVURLAsset(url: URL(fileURLWithPath: a[2]))
let out = URL(fileURLWithPath: a[3])
try? FileManager.default.removeItem(at: out)
let comp = AVMutableComposition()
let sem = DispatchSemaphore(value: 0)
Task {
  let vt = try await video.loadTracks(withMediaType: .video).first!
  let at = try await audio.loadTracks(withMediaType: .audio).first!
  let vdur = try await video.load(.duration)
  let adur = try await audio.load(.duration)
  let cv = comp.addMutableTrack(withMediaType: .video, preferredTrackID: kCMPersistentTrackID_Invalid)!
  let ca = comp.addMutableTrack(withMediaType: .audio, preferredTrackID: kCMPersistentTrackID_Invalid)!
  try cv.insertTimeRange(CMTimeRange(start: .zero, duration: vdur), of: vt, at: .zero)
  let dur = CMTimeMinimum(vdur, adur)
  try ca.insertTimeRange(CMTimeRange(start: .zero, duration: dur), of: at, at: .zero)
  let ex = AVAssetExportSession(asset: comp, presetName: AVAssetExportPresetPassthrough)!
  ex.outputURL = out
  ex.outputFileType = .mp4
  await ex.export()
  print("status", ex.status.rawValue, ex.error.map { "\($0)" } ?? "ok", "video", CMTimeGetSeconds(vdur), "audio", CMTimeGetSeconds(adur))
  sem.signal()
}
sem.wait()
